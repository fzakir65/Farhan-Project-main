# Windows built-in OCR (Windows.Media.Ocr) over a folder of page images -> one text file per image.
# Usage: powershell -ExecutionPolicy Bypass -File winocr.ps1 -InDir <folder> -OutDir <folder>
param([string]$InDir, [string]$OutDir)
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
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("en-US"))
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) { Write-Error "no OCR engine / language pack available"; exit 2 }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$files = Get-ChildItem -Path $InDir -Filter *.jpg | Sort-Object Name
$i = 0
foreach ($f in $files) {
    $out = Join-Path $OutDir ($f.BaseName + ".txt")
    if (Test-Path $out) { continue }
    try {
        $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
        $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
        $lines = $res.Lines | ForEach-Object { $_.Text }
        [System.IO.File]::WriteAllLines($out, $lines, [System.Text.UTF8Encoding]::new($false))
        $stream.Dispose()
    } catch {
        [System.IO.File]::WriteAllText($out, "[OCR ERROR] " + $_.Exception.Message)
    }
    $i++
    if ($i % 50 -eq 0) { Write-Output "$i pages" }
}
Write-Output "done: $i pages"
