param(
    [Parameter(Mandatory = $true)]
    [string]$Document,

    [string]$ExportPdf,

    [int]$ExpectedEquations = -1
)

$ErrorActionPreference = "Stop"
$documentPath = (Resolve-Path -LiteralPath $Document).Path
$word = $null
$opened = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $opened = $word.Documents.Open($documentPath, $false, $true)

    $pages = $opened.ComputeStatistics(2)
    $paragraphs = $opened.Paragraphs.Count
    $equations = $opened.OMaths.Count

    if ($ExpectedEquations -ge 0 -and $equations -ne $ExpectedEquations) {
        throw "Expected $ExpectedEquations Word equations, found $equations."
    }

    if ($ExportPdf) {
        $pdfPath = [System.IO.Path]::GetFullPath($ExportPdf)
        $pdfDirectory = [System.IO.Path]::GetDirectoryName($pdfPath)
        if ($pdfDirectory -and -not [System.IO.Directory]::Exists($pdfDirectory)) {
            [System.IO.Directory]::CreateDirectory($pdfDirectory) | Out-Null
        }
        $opened.ExportAsFixedFormat($pdfPath, 17)
    }

    [pscustomobject]@{
        document = $documentPath
        opened_without_repair = $true
        pages = $pages
        paragraphs = $paragraphs
        equations = $equations
        pdf = if ($ExportPdf) { [System.IO.Path]::GetFullPath($ExportPdf) } else { $null }
    } | ConvertTo-Json
}
finally {
    if ($opened) {
        $opened.Close($false)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($opened) | Out-Null
    }
    if ($word) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
