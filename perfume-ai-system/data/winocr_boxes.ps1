# Windows built-in OCR with WORD BOUNDING BOXES -> one JSON file per page image (used for the Curtis monograph tables,
# where column layout and the bold intensity digit matter). Usage:
#   powershell -ExecutionPolicy Bypass -File data/winocr_boxes.ps1 -InDir <folder of pNNN.jpg> -OutDir <folder> [-Pages "163-231,257-310"]
param([string]$InDir, [string]$OutDir, [string]$Pages = "")
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { Write-Error "no OCR engine / language pack available"; exit 2 }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$wanted = @{}
if ($Pages -ne "") {
    foreach ($part in $Pages.Split(",")) {
        $ab = $part.Split("-")
        $a = [int]$ab[0]; $b = if ($ab.Count -gt 1) { [int]$ab[1] } else { $a }
        for ($n = $a; $n -le $b; $n++) { $wanted[$n] = $true }
    }
}
$files = Get-ChildItem -Path $InDir -Filter *.jpg | Sort-Object Name
$i = 0
foreach ($f in $files) {
    $num = [int]($f.BaseName -replace "[^0-9]", "")
    if ($Pages -ne "" -and -not $wanted.ContainsKey($num)) { continue }
    $out = Join-Path $OutDir ($f.BaseName + ".json")
    if (Test-Path $out) { continue }
    try {
        $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
        $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
        $lines = @()
        foreach ($ln in $res.Lines) {
            $words = @()
            foreach ($w in $ln.Words) {
                $r = $w.BoundingRect
                $words += @{ t = $w.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height }
            }
            $lines += @{ text = $ln.Text; words = $words }
        }
        $json = @{ page = $num; width = $bmp.PixelWidth; height = $bmp.PixelHeight; lines = $lines } | ConvertTo-Json -Depth 6 -Compress
        [System.IO.File]::WriteAllText($out, $json, [System.Text.UTF8Encoding]::new($false))
        $stream.Dispose()
    } catch {
        [System.IO.File]::WriteAllText($out, ('{"page":' + $num + ',"error":"' + ($_.Exception.Message -replace '"', "'") + '"}'))
    }
    $i++
}
Write-Output "done: $i pages"
