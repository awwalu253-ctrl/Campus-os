<#
.SYNOPSIS
  Sanitizes a plain-SQL pg_dump (PostGIS, --no-owner --no-privileges) for restore into Supabase.

.USAGE
  .\sanitize_dump.ps1
  .\sanitize_dump.ps1 -InputPath .\local_campus.sql -OutputPath .\local_campus_sanitized.sql
  .\sanitize_dump.ps1 -RewriteExtensionRefs:$false     # skip public.geometry -> extensions.geometry rewrite

  Does not modify the input file. COPY data blocks are never touched.
#>
param(
    [string]$InputPath  = ".\local_campus.sql",
    [string]$OutputPath = ".\local_campus_sanitized.sql",
    [bool]$RewriteExtensionRefs = $true
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $InputPath)) { throw "Input file not found: $InputPath" }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$text  = [System.IO.File]::ReadAllText((Resolve-Path $InputPath), $utf8NoBom)
$lines = $text -split "`n"
$origCount = $lines.Count

# ---- Line-removal rules (applied only OUTSIDE COPY blocks) -------------------
$rules = [ordered]@{
  "CREATE EXTENSION"                  = '^\s*CREATE\s+EXTENSION\b'
  "COMMENT ON EXTENSION"              = '^\s*COMMENT\s+ON\s+EXTENSION\b'
  "ALTER EXTENSION"                   = '^\s*ALTER\s+EXTENSION\b'
  "ALTER ... OWNER TO campusos"       = '^\s*ALTER\s.*\bOWNER\s+TO\s+"?campusos"?'
  "SET SESSION AUTHORIZATION"         = '^\s*SET\s+SESSION\s+AUTHORIZATION\b'
  "SET ROLE / RESET ROLE"             = '^\s*(SET|RESET)\s+ROLE\b'
  "GRANT/REVOKE involving campusos"   = '^\s*(GRANT|REVOKE)\b.*\bcampusos\b'
  "ALTER DEFAULT PRIVILEGES"          = '^\s*ALTER\s+DEFAULT\s+PRIVILEGES\b.*\bcampusos\b'
  "CREATE SCHEMA public/tiger/topology" = '^\s*CREATE\s+SCHEMA\s+(IF\s+NOT\s+EXISTS\s+)?"?(public|tiger|tiger_data|topology)"?\s*(AUTHORIZATION\s+\S+\s*)?;'
  "ALTER SCHEMA public"               = '^\s*ALTER\s+SCHEMA\s+"?public"?\b'
  "COMMENT ON SCHEMA public/tiger/topology" = '^\s*COMMENT\s+ON\s+SCHEMA\s+"?(public|tiger|tiger_data|topology)"?\b'
  "setval on tiger/topology sequences" = "^\s*SELECT\s+pg_catalog\.setval\('\"?(tiger|tiger_data|topology)\"?\."
  "set_config('search_path')"         = "^\s*SELECT\s+pg_catalog\.set_config\(\s*'search_path'"
  "CREATE TABLESPACE"                 = '^\s*CREATE\s+TABLESPACE\b'
  "psql \restrict / \unrestrict"      = '^\\(un)?restrict\b'
}
$counts = [ordered]@{}
foreach ($k in $rules.Keys) { $counts[$k] = 0 }

# ---- Extension-schema reference rewrite (outside COPY only) ------------------
# Locally the extensions lived in public; on Supabase they live in "extensions".
$extRewrites = @(
  '(?i)\bpublic\.(geometry|geography|box2d|box3d|geometry_dump|spheroid|valid_detail)\b',
  '(?i)\bpublic\.(_?st_\w+|postgis_\w+|gist_geometry_ops\w*|gist_geography_ops\w*|spgist_geometry_ops\w*)',
  '(?i)\bpublic\.(crypt|gen_salt|digest|hmac|gen_random_bytes|encrypt|decrypt|encrypt_iv|decrypt_iv|armor|dearmor|pgp_sym_\w+|pgp_pub_\w+)(?=\s*\()'
)
$extRewriteCount = 0

$out = New-Object System.Collections.Generic.List[string]
$out.Add("SET search_path TO public, extensions;")

$inCopy = $false
$copyBlocks = 0
$setvalCount = 0
$copyTables = New-Object System.Collections.Generic.List[string]
$stray = New-Object System.Collections.Generic.List[string]

foreach ($line in $lines) {
    if ($inCopy) {
        $out.Add($line)
        if ($line -match '^\\\.\s*$') { $inCopy = $false }
        continue
    }

    if ($line -match '^COPY\s+(.+?)\s+(\(.*?\)\s+)?FROM\s+stdin;?\s*$') {
        $inCopy = $true
        $copyBlocks++
        $copyTables.Add($Matches[1])
        $out.Add($line)
        continue
    }

    $removed = $false
    foreach ($k in $rules.Keys) {
        if ($line -match $rules[$k]) { $counts[$k]++; $removed = $true; break }
    }
    if ($removed) { continue }

    if ($RewriteExtensionRefs) {
        foreach ($re in $extRewrites) {
            $m = [regex]::Matches($line, $re)
            if ($m.Count -gt 0) {
                $extRewriteCount += $m.Count
                $line = [regex]::Replace($line, $re, 'extensions.$1')
            }
        }
    }

    if ($line -match '^\s*SELECT\s+pg_catalog\.setval\(') { $setvalCount++ }
    if ($line -match '\bcampusos\b' -and $line -notmatch '^\s*INSERT\s+INTO\b') { $stray.Add($line.Trim()) }
    $out.Add($line)
}

[System.IO.File]::WriteAllText($OutputPath, ($out -join "`n"), $utf8NoBom)

# ---- Report ------------------------------------------------------------------
$body = $out -join "`n"
Write-Host ""
Write-Host "=== sanitize_dump summary ===" -ForegroundColor Cyan
Write-Host ("Input lines : {0}" -f $origCount)
Write-Host ("Output lines: {0}" -f $out.Count)
Write-Host "`nRemoved lines by rule:"
$totalRemoved = 0
foreach ($k in $counts.Keys) {
    Write-Host ("  {0,-36} {1}" -f $k, $counts[$k])
    $totalRemoved += $counts[$k]
}
Write-Host ("  {0,-36} {1}" -f "TOTAL removed", $totalRemoved)
Write-Host "`nKept / untouched:"
Write-Host ("  COPY blocks                        {0}" -f $copyBlocks)
Write-Host ("  setval() lines                     {0}" -f $setvalCount)
Write-Host ("  CREATE TABLE                       {0}" -f ([regex]::Matches($body, '(?m)^CREATE TABLE\b').Count))
Write-Host ("  CREATE INDEX                       {0}" -f ([regex]::Matches($body, '(?m)^CREATE (UNIQUE )?INDEX\b').Count))
Write-Host ("  ALTER TABLE ... ADD CONSTRAINT     {0}" -f ([regex]::Matches($body, '(?m)^ALTER TABLE\b.*\r?\n\s+ADD CONSTRAINT\b').Count))
Write-Host ("  public.* -> extensions.* rewrites  {0}" -f $extRewriteCount)

Write-Host "`nVerify manually:" -ForegroundColor Yellow
$warn = $false
if ($stray.Count -gt 0) {
    $warn = $true
    Write-Host "  - 'campusos' still appears outside COPY blocks on $($stray.Count) line(s):"
    $stray | Select-Object -First 10 | ForEach-Object { Write-Host "      $_" }
}
if ($copyTables | Where-Object { $_ -match 'spatial_ref_sys' }) {
    $warn = $true
    Write-Host "  - Dump contains COPY public.spatial_ref_sys. That table belongs to PostGIS (in 'extensions' on Supabase); remove or retarget that block."
}
$metaLeft = [regex]::Matches($body, '(?m)^\\(?!\.)\S+') | Where-Object { $_.Value -notmatch '^\\\.' }
if ($metaLeft.Count -gt 0) {
    $warn = $true
    Write-Host "  - psql meta-commands still present ($($metaLeft.Count)); the SQL Editor will reject them."
}
if ($copyBlocks -gt 0) {
    $warn = $true
    Write-Host "  - $copyBlocks COPY ... FROM stdin block(s) present: the Supabase SQL Editor CANNOT run these. Use psql against the Supabase connection string."
}
if (-not $warn) { Write-Host "  - nothing flagged" }
Write-Host "`nWrote: $OutputPath" -ForegroundColor Green