# Step 4: Build the one-page report

The student gets one file: `evidence-report.html`. It is a single page they can click through, with every quote and its link, the items that were not counted and why, and five questions to take into interviews. Nothing else is handed over. No separate notes file, no checked ledger.

You don't write the page and you don't decide the labels. You fill in a data file, and a script builds the page and works out each label from the items. That keeps the wording plain and the labels mechanical: if you doubt an item, that belongs in its result or its note, never in a nudge to the label.

## 1. Write the data

Create `report.json` in your working folder with this shape. Every item from the check goes in: the ones that count, the ones set aside and the ones removed.

```json
{
  "idea": "one neutral sentence, as in the ledger",
  "date": "2026-10-05",
  "who_counts": "one sentence, as in the ledger",
  "assumptions": [
    {
      "statement": "the hypothesis exactly as the student confirmed it",
      "needs_number": false,
      "still_open": "one plain sentence on what is still missing",
      "not_found": ["one plain sentence per thing the search looked for and didn't find"],
      "unread": {"for": 0, "against": 0},
      "items": [
        {
          "side": "for",
          "result": "counts",
          "reason": "",
          "kind": "own words",
          "quote": "the exact words from the page, without quotation marks around them",
          "who": "name as the page shows it",
          "when": "date on the page, or: no date shown",
          "where": "site and kind of page, e.g. Trustpilot review",
          "did": "what the person did, in a few plain words. Leave empty if they only gave an opinion",
          "note": "a caveat the student should know, or leave empty",
          "link": "https://...",
          "voice": "a short name for the person or study; the same for two items by the same one",
          "found_in_check": false
        }
      ]
    }
  ],
  "interviews_only": [{"statement": "...", "reason": "as in the ledger"}],
  "not_checked": ["any searchable hypothesis the ledger lists as not checked this time"],
  "products": [{"name": "...", "link": "https://...", "fact": "one fact its own page states"}],
  "unread_pages": {"count": 0, "wouldnt_open": [{"site": "...", "link": "https://..."}]},
  "talk_to": "the group the hypotheses name",
  "questions": [{"text": "...", "tests": "Assumption 1"}],
  "checked": {"searches": 0, "pages_read": 0}
}
```

How to fill it:

- **`side`** is `for`, `against` or `context`. **`result`** is `counts`, `set aside` or `removed`. A context item that passed the check has side `context` and result `counts`.
- **`reason`** is the code from step 3 for anything set aside or removed, and empty for anything that counts. The page turns each code into a plain sentence, so don't write your own.
- **`kind`** is `own words`, `number` or `organisation fact`. For a number or an organisation fact, use `who` for who counted and `did` for what exactly was counted.
- **`needs_number`** is `true` when the hypothesis is about how many or how often ("most", "often", "a lot"). People's stories show that something happens, not how often, so the script only lets a counted number settle those.
- **`note`** carries doubts in plain words: "Other people in the thread suspected this was an advert. Nothing confirmed it." If the words are a reporter's and not a direct quote, say "As reported by <outlet>, in the reporter's words."
- **`unread`** is how many found-but-unread pages the ledger lists for each side of that assumption. **`unread_pages.count`** is the total, and `wouldnt_open` lists up to three that failed to open.
- **`checked`** adds the research and the check together.
- **`products`** has four at most, each stated the way its own page states it, including a free plan if the page shows one.
- Write everything in plain words. No item numbers such as E3, no "ledger", "cell" or "audit".
- Keep `who`, `when`, `where` and `did` to a few words each, and `note` to one sentence. The page is read by a student in a hurry.

Never write "nothing found" in `not_found` about something that was found and set aside. Those items are already on the page under "Not counted, and why".

## 2. Write five interview questions

They ask what people did, not what they would do. Ask about the past and about specifics: "Tell me about the last time...", "What did you do about it?", "What did that cost you?", "What have you tried and stopped using, and why?". Never "Would you use..." or "Would you pay...". Each is one full sentence holding one question.

Aim them at the assumptions where the web was split or thin first, then at the interview-only ones. In `tests`, write "Assumption 1", or a few words naming the interview-only assumption.

## 3. Build the page

Run the script that sits in this skill's folder:

```
python <this skill's folder>/scripts/build_report.py report.json evidence-report.html
```

Write `evidence-report.html` wherever files you share with the student go. If the script lists problems, fix the data and run it again. Don't edit the page by hand and don't work around the script: the problems it lists are the report's own rules.

The script prints the label it worked out for each assumption. Those are the only labels to repeat to the student.

## 4. Hand it over

Share `evidence-report.html` and nothing else. Then say, in three or four short lines:

- the page is ready, and they can click each assumption to see the quotes
- the label for each assumption, in the script's words, with how many people and pages it rests on
- that the page doesn't say whether the idea is good, and the next step is the interviews

Don't repeat the evidence in the chat, and don't add a view on the idea. If the student asks whether the idea is good, say the page can't answer that and point them to the questions.
