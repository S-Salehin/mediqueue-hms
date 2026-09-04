param(
    [Parameter(Mandatory = $true)]
    [string]$DocumentPath,

    [Parameter(Mandatory = $true)]
    [string]$PdfPath
)

$resolvedDocument = (Resolve-Path -LiteralPath $DocumentPath).Path
$resolvedPdf = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PdfPath))
$pdfDirectory = Split-Path -Parent $resolvedPdf
New-Item -ItemType Directory -Path $pdfDirectory -Force | Out-Null

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.Options.UpdateFieldsAtPrint = $true
    $document = $word.Documents.Open($resolvedDocument, $false, $false)

    $document.Repaginate()
    [void]$document.Fields.Update()

    foreach ($storyType in 1..17) {
        try {
            $story = $document.StoryRanges.Item($storyType)
            while ($null -ne $story) {
                [void]$story.Fields.Update()
                $story = $story.NextStoryRange
            }
        }
        catch {
            # Some story ranges do not exist in a document. This is normal.
        }
    }

    foreach ($toc in $document.TablesOfContents) {
        $toc.Update()
    }
    foreach ($tableOfFigures in $document.TablesOfFigures) {
        $tableOfFigures.Update()
    }

    $document.Repaginate()
    $document.SaveAs2($resolvedDocument, 16)
    $document.ExportAsFixedFormat($resolvedPdf, 17)
    Write-Output "Finalized DOCX: $resolvedDocument"
    Write-Output "Rendered PDF: $resolvedPdf"
}
finally {
    if ($null -ne $document) {
        $document.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
