# Smoke Test (preview 0.2.2)

Part of Leverage by BCE. Designed and built by Nayan Kanaparthi, AI Graduate Assistant at the Berkley Center for Entrepreneurship, NYU Stern.

Start a chat, attach your findings PDF, and type: "use the smoke-test skill to plan my smoke test".
For an independent check, open a new chat, upload smoke-test-plan.md, and type: "check my smoke test plan".
After the test has run, open a new chat, upload smoke-test-plan.md, and type: "read my smoke test results".

Needs code execution turned on (Settings > Capabilities). Posts are drawn with Pillow; where it isn't available they come as HTML at the exact size.

What's new in 0.2: the launch pack is designed for the product. Claude proposes two looks first, following Anthropic's frontend-design guidance, and you pick one. Posts and print pieces come out as exact-size images with bundled fonts. Every image slot gets a prompt for your own image tool (ChatGPT, Gemini, Adobe or Canva), and a quality gate runs before anything is shown.

What's new in 0.2.2: before designing anything, Claude asks how your brand should look (colours, three words for the feel, a brand your customers trust, anything you already have), or you can say "pick for me". The two looks it proposes come from your words and your customers' world, and a check refuses the look AI tools give every product. Asking for a different look later rebuilds the whole pack, not just a colour. The page now carries its own typeface files, so it shows the same faces as the posts with nothing loaded from another site. Print pieces get a QR code once you come back with the published page's address. If reach is short, Claude asks about it before you lock. And when the reason for your pass line is an AI's guess, the plan says so.

Third-party notices: skills/smoke-test/licenses/NOTICE.md.
