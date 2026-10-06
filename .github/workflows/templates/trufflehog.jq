# Resumen en Markdown de TruffleHog (salida --json, leída con jq -s).
# Nunca muestra el secreto: solo el detector, si está verificado y dónde está.
# Entrada: lista de hallazgos. Argumento: $blob (URL base .../blob).

def cell: tostring | gsub("\\|"; "\\|") | gsub("[\r\n]+"; " ");

map(select(type == "object" and has("DetectorName")))
| if length == 0 then
    "No secrets found."
  else
    "**\(length) finding(s).**",
    "",
    "| Detector | Verified | Location | Commit | Author |",
    "| --- | --- | --- | --- | --- |",
    (.[]
     | (.SourceMetadata.Data.Git // {}) as $git
     | ($git.commit // "") as $commit
     | ($git.file // "") as $file
     | ($git.line // 0) as $line
     | "| \(.DetectorName | cell) "
       + "| \(if .Verified then "yes" else "unknown" end) "
       + "| [\($file | cell):\($line)](\($blob)/\($commit)/\($file | gsub("\\|"; "%7C"))#L\($line)) "
       + "| `\($commit[0:12])` "
       + "| \($git.email // "" | cell) |")
  end
