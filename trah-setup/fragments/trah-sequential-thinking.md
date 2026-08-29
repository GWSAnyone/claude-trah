---
{
  "id": "trah-sequential-thinking",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 190,
  "why": "когда размышление вслух окупается, и почему оно не заменяет чтения кода",
  "covered_by": []
}
---
## sequential-thinking

Use it where an error in reasoning costs more than the time spent on it:
architectural forks, the blast radius before an edit across several modules,
debugging where the symptom is far from the cause, data migrations, untangling
contradictory observations.

For straightforward tasks it is noise. Skipped it deliberately — say so in one line.

Thinking does not replace reading the code: the blast radius is established by
`find_referencing_symbols`, not by musing about who might be calling the function.
