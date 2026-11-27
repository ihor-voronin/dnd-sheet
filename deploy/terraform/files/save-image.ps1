# Образ у стиснутий архів для сервера: `docker save` + gzip.
# Terraform викликає його з local-exec без cmd — шляхи не ламаються лапками.
# docker load на сервері сам розпізнає gzip; архів ~4.5 раза менший за tar.
param(
    [Parameter(Mandatory)][string]$Image,
    [Parameter(Mandatory)][string]$Output
)
$ErrorActionPreference = "Stop"

$tar = "$Output.tmp.tar"
docker save -o $tar $Image
if ($LASTEXITCODE -ne 0) { throw "docker save $Image не вдався" }

$source = [System.IO.File]::OpenRead($tar)
$target = [System.IO.File]::Create($Output)
try {
    $gzip = New-Object System.IO.Compression.GZipStream($target, [System.IO.Compression.CompressionLevel]::Optimal)
    try { $source.CopyTo($gzip) } finally { $gzip.Dispose() }
} finally {
    $source.Dispose()
    $target.Dispose()
}
Remove-Item $tar
"{0}: {1:N0} MB" -f (Split-Path $Output -Leaf), ((Get-Item $Output).Length / 1MB)
