using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Text.RegularExpressions;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

var cfg = builder.Configuration;
var frontendOrigin = cfg["FrontendOrigin"] ?? "http://localhost:5173";
var viewerBaseUrl = cfg["ViewerBaseUrl"] ?? "http://localhost:8000";
var jwtSecret =
    cfg["Jwt:HmacSecret"]
    ?? throw new InvalidOperationException("Jwt:HmacSecret is required");
var jwtIssuer = cfg["Jwt:Issuer"] ?? "back-office";
var jwtTtlSeconds = int.Parse(cfg["Jwt:TtlSeconds"] ?? "300");
var bucket = cfg["S3:Bucket"] ?? "kyc-docs";
var s3Internal = cfg["S3:Endpoint"] ?? "http://localhost:9000";
// The PublicEndpoint is the URL the browser uses to PUT directly to MinIO. When
// the backend runs inside docker, this differs from the in-cluster endpoint —
// e.g. `http://minio:9000` internally, `http://localhost:9000` from the browser.
var s3Public = cfg["S3:PublicEndpoint"] ?? s3Internal;
var s3Region = cfg["S3:Region"] ?? "us-east-1";
var s3Key = cfg["S3:AccessKey"] ?? "minio-user";
var s3Sec = cfg["S3:SecretKey"] ?? "minio-password";

builder.Services.AddCors(o =>
    o.AddDefaultPolicy(p => p.WithOrigins(frontendOrigin).AllowAnyHeader().AllowAnyMethod())
);

var creds = new BasicAWSCredentials(s3Key, s3Sec);
AmazonS3Client BuildS3(string endpoint) =>
    new(
        creds,
        new AmazonS3Config
        {
            ServiceURL = endpoint,
            ForcePathStyle = true, // MinIO requires path-style addressing
            AuthenticationRegion = s3Region,
        }
    );

var s3 = BuildS3(s3Internal); // reads (ListObjects, EnsureBucket)
var s3Sign = BuildS3(s3Public); // presigning — host is part of the signed payload

var app = builder.Build();
app.UseCors();

// Make sure the bucket exists on startup. Idempotent.
try
{
    await s3.PutBucketAsync(new PutBucketRequest { BucketName = bucket });
    app.Logger.LogInformation("Created bucket {Bucket}", bucket);
}
catch (AmazonS3Exception e)
    when (e.ErrorCode is "BucketAlreadyOwnedByYou" or "BucketAlreadyExists")
{
    // already there — fine
}

app.MapGet("/healthz", () => Results.Ok(new { ok = true }));

app.MapPost(
    "/api/uploads",
    (UploadRequest req) =>
    {
        if (!IsValidUser(req.User))
            return Results.BadRequest(new { error = "invalid user" });
        if (string.IsNullOrWhiteSpace(req.FileName))
            return Results.BadRequest(new { error = "fileName required" });

        var safeName = Path.GetFileName(req.FileName);
        var key = $"users/{req.User}/{Guid.NewGuid():N}/{safeName}";
        var contentType = string.IsNullOrWhiteSpace(req.ContentType)
            ? "application/octet-stream"
            : req.ContentType;

        // AWS SDK defaults presigned URLs to HTTPS; honour the scheme on the
        // ServiceURL instead (MinIO in dev is plain HTTP).
        var protocol = s3Public.StartsWith("https://", StringComparison.OrdinalIgnoreCase)
            ? Protocol.HTTPS
            : Protocol.HTTP;
        var url = s3Sign.GetPreSignedURL(
            new GetPreSignedUrlRequest
            {
                BucketName = bucket,
                Key = key,
                Verb = HttpVerb.PUT,
                Expires = DateTime.UtcNow.AddMinutes(10),
                ContentType = contentType,
                Protocol = protocol,
            }
        );
        return Results.Ok(new { uploadUrl = url, objectKey = key, contentType });
    }
);

app.MapGet(
    "/api/documents",
    async (string user) =>
    {
        if (!IsValidUser(user))
            return Results.BadRequest(new { error = "invalid user" });
        var resp = await s3.ListObjectsV2Async(
            new ListObjectsV2Request { BucketName = bucket, Prefix = $"users/{user}/" }
        );
        var docs = (resp.S3Objects ?? new List<S3Object>()).Select(o => new
        {
            key = o.Key,
            name = Path.GetFileName(o.Key),
            size = o.Size,
            lastModified = o.LastModified,
        });
        return Results.Ok(docs);
    }
);

app.MapPost(
    "/api/viewer-token",
    (ViewerTokenRequest req) =>
    {
        if (!IsValidUser(req.User))
            return Results.BadRequest(new { error = "invalid user" });
        if (string.IsNullOrWhiteSpace(req.ObjectKey))
            return Results.BadRequest(new { error = "objectKey required" });

        var now = DateTime.UtcNow;
        var iatUnix = new DateTimeOffset(now).ToUnixTimeSeconds();
        var signKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret));
        var signing = new SigningCredentials(signKey, SecurityAlgorithms.HmacSha256);

        // JwtSecurityToken populates iss / nbf / exp from the constructor params,
        // but iat must be added as an explicit numeric claim or PyJWT will reject
        // the missing iat.
        var token = new JwtSecurityToken(
            issuer: jwtIssuer,
            notBefore: now,
            expires: now.AddSeconds(jwtTtlSeconds),
            claims: new[]
            {
                new Claim(JwtRegisteredClaimNames.Sub, req.User),
                new Claim("obj", req.ObjectKey),
                new Claim("case", string.IsNullOrWhiteSpace(req.Case) ? "default" : req.Case),
                new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString("N")),
                new Claim(
                    JwtRegisteredClaimNames.Iat,
                    iatUnix.ToString(),
                    ClaimValueTypes.Integer64
                ),
            },
            signingCredentials: signing
        );

        var encoded = new JwtSecurityTokenHandler().WriteToken(token);
        return Results.Ok(
            new { token = encoded, embedUrl = $"{viewerBaseUrl}/embed/{encoded}" }
        );
    }
);

app.Run();

static bool IsValidUser(string? user) =>
    !string.IsNullOrWhiteSpace(user)
    && user.Length <= 64
    && Regex.IsMatch(user, @"^[A-Za-z0-9._\-]+$");

record UploadRequest(string FileName, string ContentType, string User);

record ViewerTokenRequest(string ObjectKey, string User, string? Case);
