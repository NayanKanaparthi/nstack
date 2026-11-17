# The launch pack

The launch pack is the main thing the student takes away: everything they need to go out and run the test, for **their** product, group and channel. It must look like a real team made it for this product. A generic template is a failure, and so is Claude's default look.

Never show internal test ids (like T6) or "strength x of 5". Use the test's plain name and the plain "how convincing" words.

Before designing anything, read `references/design/frontend-design.md` (Anthropic's frontend-design guidance). It governs the page, the posts and every printed piece.

## 1. The look comes first

**Ask before you design.** Send the brand question from SKILL.md Step 5 and wait. Write the answer into `smoke-work.json` as `look_brief`, in the student's own words. If they upload a logo or photos, look at them and take their colours and shapes from what you see.

From the plan, write down the product, the audience (the persona and the group on the card) and the one job every asset has: getting a stranger to do the act on the card.

**Where the look comes from, in this order:**
1. **The student's words:** colours, the feel, a brand they named, what they uploaded. Their words always win, including over the AI-default list. If their colours can't make readable text, keep them as accents and say so in one line. A brand, school or office they name gives the feel (calm, bold, plain), never its logo, name, wordmark or exact layout: the pack must not be mistaken for theirs (hard rule 13).
2. **Their customers' world:** where the group on the card works or shops, what they read, what they handle in a normal week, and what they already trust and pay for. Name 2 or 3 concrete things from it that someone from that world would know at a glance: an object, a document, a place. These go in `drawn_from`. Work them out from this team's findings file and the student's words. This file gives no examples on purpose, because an example here ends up in every team's pack.
3. **The product's own world:** its material, place, routine or object.

Never take the look from a sample pack, from another team's pack, or from what you would make for any product. Test it: if a different product could wear this look just as well, it isn't finished.

With "pick for me", both directions come from 2 and 3.

Draft **two directions**, A and B, each as a short design plan in the frontend-design format:
- **Colour:** 4 to 8 named hex values.
- **Type:** one or two typefaces with their roles. Pick only from the bundled fonts (`python3 scripts/postkit.py fonts`). The page carries the same files (section 3), so the page and the posts show the same faces.
- **Layout:** one sentence plus an ASCII wireframe for the page's first screen and for the main piece. The main piece is the first thing a stranger sees in the card's channel: the post for a social channel, the printed card or flyer for walk-ins. With two channels, it is the one expected to reach more people. The wireframes stay in your plan; they don't go into any deliverable.
- **The one memorable element:** taken from the product's own world (its material, place, routine or object), not decoration.
- **Image slots:** where the student's images go, if a piece needs any.
- **Drawn from:** one line naming what in the student's words or their customers' world this direction comes from.

A stays closest to the student's words. B is a real alternative from the same customers' world that they might not have thought of. The two directions must differ in more than colour.

Review both against frontend-design's calibration list (the five AI-default clusters) and against the brief. Revise anything that reads as a default, and say in one line what you changed.

**Write each direction down and check it before you draw it.** Write `look-A.json` and `look-B.json` next to `card.json`:

```json
{
  "student_words": "<their answer to the brand question, word for word, or: pick for me>",
  "drawn_from": ["<a thing from their customers' world, in 3 words or more>", "<another>", "<a third, if there is one>"],
  "name": "<two or three words for this look>",
  "colours": [
    {"name": "<plain name>", "hex": "<#RRGGBB>", "role": "background"},
    {"name": "<plain name>", "hex": "<#RRGGBB>", "role": "text"},
    {"name": "<plain name>", "hex": "<#RRGGBB>", "role": "accent"},
    {"name": "<plain name>", "hex": "<#RRGGBB>", "role": "support"}
  ],
  "type": [{"family": "<a bundled typeface>", "role": "<what it is used for>"}],
  "memorable": "<the one memorable element, from the product's own world>"
}
```

- 4 to 8 colours: exactly one `background`, exactly one `text`, at least one `accent`; the rest are `support`.
- 1 or 2 bundled typefaces.

Run `python3 scripts/smoke.py look --in look-A.json`, then the same for B. It refuses a look with no student answer, a look drawn from nowhere, unreadable text, and the two AI-default looks that colour alone can show. Fix what it names and run it again. If it says the student must confirm a very common look they asked for, ask them that one question. Draw nothing until both print `LOOK OK`.

Then render each direction as its own image, `look-A.png` and `look-B.png` (1600 x 900 each, with `scripts/postkit.py` and that direction's `look=` file). The left half shows the palette chips with their names, the headline in its typeface and the "Drawn from" line. The right half shows the main piece, large enough to judge. Keep the words on the sheet few; say the idea behind each look in the chat.

Stop: **"Which look do you want, A or B? You can mix them or change anything."**

Save the pick as `look.json`. For a mix or a change, write the new `look.json` and run the check on it before you build.

From here on, every colour and typeface in every piece comes from `look.json`:
- every image: `postkit.Canvas(width, height, bg=..., look="look.json")`, so the report shows `OFF LOOK` for anything that drifts. Take the colours and typefaces from `postkit.look_parts("look.json")`, never typed by hand. For shapes drawn through `.draw`, take each colour from `c.colour("#RRGGBB")` so it is checked too. Run your drawing scripts with `python3 -B`;
- the page: `python3 scripts/smoke.py look --in look.json --page <the page file>` must pass. It reads the page's colours (hex, `rgb()`, `hsl()` and the basic colour names) and its `font-family` lines, and it checks that the page carries the look's typeface files (section 3).

**A different look is a redo.** When the student asks for a different look or names who it should appeal to, add their words to `look_brief`, draft two new directions from this section's start, check them, show them, and rebuild every piece in the one they pick. Changing only the words or one colour is not an answer.

## 2. Images: the student's own tool makes the photos

Claude doesn't make photo-style images in this chat. So wherever a piece needs a photo, it has a named image slot (for example `hero-photo`, `post-a-photo`). For each slot, write one prompt in `image-prompts.md`:
- the slot name and where it is used;
- the exact aspect ratio of the slot itself, as drawn in the layout (for a full-bleed post that is 4:5, for a story 9:16, for a LinkedIn link image 1.91:1);
- the product exactly as the team could really make it;
- a real setting where the group lives or works, with light direction and mood matching the chosen look;
- no text and no logos in the image (the layout adds the text);
- the side to keep clear for text.

Add one line per tool, without promising features or limits:
- ChatGPT (ask for the aspect ratio and "no text");
- Gemini;
- Adobe Express or Firefly (NYU may provide access; check);
- Canva's image tool.

For software and B2B products, the real product screen usually beats a photo. Build that screen yourself in HTML or SVG in the chosen look, using the product's real wording. It is the product, not decoration. A piece built around that screen needs no photo slot.

Until images are added, each slot shows a quiet placeholder naming the slot (postkit draws it). Never fill a slot with a fake drawing pretending to be the product.

Every asset must already work as a finished piece before any image arrives. Either the slot takes at most about 40% of the canvas, with typography and the memorable element carrying the rest, or there is a typographic version that ships without an image. Student images go in `images/` at the top of the pack for posts and print, and in `landing-page/images/` for the page.

When the student uploads images, put them in the slots, re-render the page and posts, make `landing-page.zip` again, and send the updated files.

## 3. The page

Build `landing-page/index.html` from the chosen look, following frontend-design's process: the plan, the check against the brief, then the build.
- **Typefaces:** run `python3 scripts/smoke.py fonts --in look.json --to landing-page`. It copies the look's typeface files into `landing-page/fonts/` and prints the `@font-face` lines. Paste those lines at the top of the page's `<style>`, and name the typefaces exactly as it prints them, first in each `font-family`, with a system fallback after. Use only the weights it lists. Don't load typefaces from Google Fonts or any other site: a wrong name there drops the typeface with no error, and the look check refuses it.
- **Images:** `<img src="images/<slot>.jpg">`. The page must be publishable as it is, before the student adds a single image: when a file is missing, that slot shows nothing to a visitor (it collapses, or a concept drawing made in the look takes its place). A slot's name never shows on the page. Slot names belong in the pack's preview and in `image-prompts.md`.
- **The first screen:** the one memorable element from the look sits on the first screen, next to the headline. It never waits below the fold.
- **Layout:**
  - one headline, plus the line right under it; together they say what it is and who it's for;
  - 2 or 3 specific benefits written as goals ("designed to");
  - the price, if the test is about wanting or paying;
  - one primary action;
  - no navigation.
- **Variants** switch with `?v=<name>`, and only one thing changes between them. **Sources** come from `?src=<channel>`, so each channel counts on its own.
- **The honest screen:** the primary action opens "We haven't made it yet. We're a student team testing whether people want this before we make it. Nothing was charged." Then the signup or booking link, and the privacy note. Unless the student gives their own wording, the note reads: "We'll use this only to contact you about [product]. We won't share it, and we'll delete it if you ask."
- **A config block at the top:** one Tally link per variant, plus an optional GoatCounter code. Until the links are pasted in, the page shows a "preview only" note.
- **Counting visits (the denominator):** GoatCounter is free for reasonable public use, needs no cookies and is added with one script tag. When the code is set, the page counts each visit as `v=<variant>/src=<source>` with `goatcounter.count({path: ...})`. Check that call before class. If the team skips GoatCounter, count visits per source with one click-counting short link per variant and source, plus Instagram's landing page views for ads.
- **No BCE credit on public assets.** The page, posts and print pieces are the team's own marketing, so they carry no Leverage by BCE footer. The page keeps the credit only in an HTML comment.
- **Quality floor:** responsive down to 390 pixels wide, visible focus, 4.5:1 contrast for body text, reduced motion respected. Use motion only for one orchestrated moment, or none.
- **Footer:** "[Product] is in development by a student team." No reviews, counts, logos or press.

If this environment has a browser tool, look at the page at 390 and 1280 pixels wide and fix what you see. Open the file from inside `landing-page/`, so it finds its `fonts/` folder. If there is no browser, run the quality gate (section 8) by reading the code.

## 4. Posts, ads and printed pieces

Draw each one as a PNG at the exact platform size with `scripts/postkit.py`. Run `python3 scripts/postkit.py help` once for its full API and its limits:
- text smaller than 2.2% of the canvas width is flagged;
- the safe margin is 6% of the short side;
- contrast is 4.5:1, or 3:1 for text 48px and over.

Make only the pieces the card's channel uses: posts when it uses a social feed, print pieces when it uses print (walk-ins, flyers, a pop-up). Write one short script per asset:

```python
import sys; sys.path.insert(0, "<this skill's folder>/scripts")
from postkit import Canvas, SIZES, look_parts
bg, ink, accents, supports, faces = look_parts("look.json")
c = Canvas(*SIZES["instagram-post"], bg=bg, look="look.json")
c.text((90, 110, 990, 470), "<the headline>", faces[0], "Regular", 120, color=ink, on=bg)
c.image((90, 520, 990, 1120), "images/post-a-photo.jpg", slot="post-a-photo")
c.save("posts/post-a.png")
```

- **Sizes:** `instagram-post` 1080 x 1350, `story` 1080 x 1920, `linkedin-post` 1200 x 627, `linkedin-square` 1200 x 1200, `card-quarter-letter` 1275 x 1650 (4.25 x 5.5 in), `card-4x6`, `flyer-letter`. Print pieces are saved with `pdf=True` at 300 dpi.
- **Consistency:** same look as the page. Variants change one thing only (the design, the message or the price).
- **Headlines on a 1080-wide canvas:** at least 64 pixels. Every word must be readable on a phone held at arm's length.
- **The report:** `save()` prints one, and every OVERFLOW, LOW CONTRAST, SMALL TEXT, MARGIN and OVERLAP note must be fixed before you show anything. If you can view images, look at each PNG and refine it once: make what is there more precise, and don't add more.
- **QR codes on print pieces:** `c.qr(box, address)` draws one in the look's own dark and light colours, with nothing to install. The address is the published page's, with `?src=<the print channel>` so scans count on their own. The page isn't published when you first make the pack, so pass `None`: it draws a placeholder, and the launch steps tell the student to come back with the address. When they do, run the script again with the address and send the print file, and remind them in one line to print only once the page no longer shows its "preview only" note. Give the code a box at least 2 cm wide in print (240 pixels at 300 dpi), and fix any `QR CODE` line in the report.
- **Without Pillow,** make each asset as an HTML file at the exact pixel size, and tell the student to export it (a screenshot or Canva).
- **Canva:** if this chat has Canva tools, say in the three-line summary that editable Canva versions of the posts are available if they ask. It is a statement, not a second question. Make them only when the student asks.

## 5. The words

- 3 taglines.
- One caption per variant, when the channel uses posts: the same message, only the variant line changes, and "I'm building this" included.
- Alt text for every image.
- **For B2B:** a LinkedIn post. Where email is a channel on the card, add a cold email under 120 words, with an accurate sender, an honest subject, a postal-address line and "Reply 'no thanks' and I won't write again."
- **For walk-ins:** a 20-second script, with the one question to ask before handing over the card.

## 6. Launch steps, specific to their channel

Number the steps, with minutes and dollars for each.
- **Email list or booking:** Tally. Its free plan allows unlimited responses and shows form visits. Use one form per variant (or hidden fields), one email field, and the privacy note.
- **Publishing:** unzip `landing-page.zip` and put the `landing-page` folder (with `index.html`, `fonts/` and `images/`) on Netlify Drop. No account is needed to publish; sign up to keep the site. Give the address for each variant and source.
- **If the pack has a printed piece:** "Come back to this chat with the page's address, and I'll put the QR code on the card and send you the print file." Print nothing before that.
- **Understanding check:** show the page to 10 strangers and ask, "In your own words, what is this and what does it cost?" Fix the headline if fewer than 8 get it.
- **Instagram boost (consumer):**
  - A creator or business account is required.
  - Use the goal "More website visits", with one boost per variant, each on its own link.
  - Use a custom audience built from the persona: location, age and interests.
  - Spend about $5 a day per variant. Meta recommends at least $5 a day; check the minimum in the app.
  - Start all variants on the same day with the same audience, and don't edit them mid-run.
- **LinkedIn (B2B):** a post from a team member's profile, plus personal one-to-one messages to people in the buying role. Personal messages are fine; bulk or automated messages are not.
- **Communities:** name 3 kinds of places, and read their rules first. Write a post that asks and learns, with "I'm building this". If links aren't allowed, don't post the link.
- **Count every day** with the tracking sheet, then **stop and read** at the number of people needed or on the end date.

## 7. Tracking sheet and honesty checklist

- **`tracking-sheet.csv`:** date, variant, source, people reached, the act, friends and classmates in their own column, and notes.
- **The honesty checklist:** in plain words, for this test, from the plan.

## 8. Quality gate (run it before you show the pack)

Check every asset and fix what fails:
1. **No AI-default look.** `smoke.py look` printed `LOOK OK` for the look in use. None of frontend-design's five AI-default clusters in the page or post design unless the student asked for one in their own words (a colour that is the product's own, shown in its photo, doesn't count):
   - cream with terracotta;
   - near-black with one neon accent;
   - broadsheet hairlines;
   - the identical-card SaaS kit;
   - template chrome: all-caps eyebrows, middle-dot strings, monospace labels, arrows on buttons.
2. **One memorable element** from the product's world, on the page's first screen and on the main piece, with everything else quiet. The memorable element, the accent colour and the headline typeface each come from something in `drawn_from`, and the pack's "chosen look" section says which. Support colours and a plain reading typeface need no source.
3. **The same look** on the page, the posts and the print pieces: no `OFF LOOK` line in any postkit report, and `smoke.py look --page` passes for the page, which also means the page carries its typeface files in `landing-page/fonts/`.
   - **Their look, not anyone's:** the "chosen look" section of the pack shows the student's own words and the "Drawn from" line.
4. **Readable on a phone:** headlines, buttons and prices.
5. **A clean postkit report** for every image, at the exact sizes. `launch-pack.html` itself reads at 390 pixels wide with no sideways scroll.
6. **Every image slot named,** each with its prompt in `image-prompts.md`. On the page itself, no slot name or grey placeholder shows to a visitor. A print piece's QR code is either drawn from the published address or still the placeholder, with the launch step that says to come back.
7. **Honesty elements visible:**
   - "I'm building this";
   - the honest screen;
   - the privacy note;
   - a "Concept design" label wherever a product that doesn't exist yet is shown;
   - nothing that could be taken for a real organisation's own page, post or notice (hard rule 13).
8. **Numbered markers only for a real sequence.**

## 9. Extras, only where they apply

- **Claude Design** (Pro, Max, Team and Enterprise): write `design-brief.md` (the chosen look, the content, the sizes and the honesty rules). The student can paste it into Claude Design and export to Canva or HTML.
- **Reels and video tests:**
  - Always: a script with a hook in the first 2 seconds, plus 4 to 6 storyboard frames drawn with postkit at 1080 x 1920 in the chosen look.
  - Only if the student works in the desktop app or Claude Code with Node 22+ and FFmpeg: mention HyperFrames (open source, Apache 2.0). It can turn frames into an MP4, and the student runs it themselves.

## Hard rules (never optional)

1. No card details in a fake checkout. Stop at add-to-cart.
2. Every buy, demo or download button leads to the honest screen in the same flow.
3. **If money is taken:**
   - a ship date the team has grounds for, or shipping within 30 days;
   - an offer to cancel;
   - a refund within 7 working days (FTC Mail Order Rule).
4. No made-up testimonials, user counts, logos, press or reviews.
5. Posts about their own idea say "I'm building this". Friends who share it disclose the connection.
6. No claim without evidence. Benefits are goals.
7. A privacy note under every email or phone field.
8. Cold email follows CAN-SPAM: sender, subject, postal address, and an opt-out honoured within 10 business days.
9. **AI images:**
   - labelled where the platform requires it;
   - showing only what the team could really make;
   - never on a Kickstarter hardware page.
10. The post and the page promise the same thing.
11. No bulk or cold DMs.
12. No interviewee names or quotes in anything public without the person's OK.
13. Never imitate a real organisation closely enough to be taken for it: no copied logo, name or wordmark, and nothing that reads as an official notice from a school, a landlord, a company or an agency. The page and every piece say who is behind it ("a student team").

## How to deliver it

**`launch-pack.html`:** shows everything in order, readable on a phone, with every image embedded:
1. the test on one page;
2. the chosen look, with the student's words about it and what it is drawn from;
3. the page (screenshots if you can take them, otherwise the file link);
4. the posts and print pieces;
5. the words;
6. the image prompts;
7. the launch steps;
8. the checklist.

**Next to it:**
- `landing-page/` (with `index.html`, `fonts/` and `images/`), and the same folder zipped as `landing-page.zip` so it downloads as one file with its folders intact (`python3 -c "import shutil; shutil.make_archive('landing-page', 'zip', '.', 'landing-page')"`, run in the download folder);
- `posts/` (only when the channel uses posts);
- `print/` (only when the channel uses print);
- `images/` (the student's images for posts and print);
- `image-prompts.md`;
- `tracking-sheet.csv`;
- `smoke-test-plan.md`;
- `design-brief.md` where it applies.

**Credit footer:** "Leverage by BCE · Designed and built by Nayan Kanaparthi · Berkley Center for Entrepreneurship, NYU Stern · Smoke Test 0.2.2". It goes on the internal files only: `launch-pack.html`, the plan, `image-prompts.md` and `design-brief.md`. It never goes on the page, posts or print pieces.
