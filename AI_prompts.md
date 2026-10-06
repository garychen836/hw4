# HW 4 AI Prompt Log

This file records the prompts I typed to my vibe coder for HW 4 (Campus Customs website: React + Vite TypeScript front end, FastAPI backend with a PydanticAI agent). Each problem has its own section with the problem number and title. Inside each section, every prompt is its own numbered entry, labeled as the **first prompt**, a **follow-up prompt** (with one sentence on what was lacking after the prompt before it), an **additional prompt**, or a **sanity check** against the rubric. Prompts are copied word for word (typos included); screenshots I attached are described in brackets.

---

## Setup — Scenario and data

### Prompt 1 — Get the data

> ok, let's start with HW4, here is the scenario. Find data(2) in my download folder and move it to the HW4 folder and unzip there — [screenshot of the Scenario and data section]

### Prompt 2 — Reuse the environment and API key

> btw, pull teh .venv etc from other HW/Lec folder to make sure you will have access to the api key later on

---

## Problem 1 — Vibe coder prompts

### Prompt 1 (first prompt)

> similar to previous work, lets have a prompt file first, that will record and update all my prompts

### Prompt 2 (follow-up prompt, sanity check)

> the prompt creation is P1. let's sanity check - — [screenshots of Problem 1 Panel A and Panel B]

**What was lacking:** The prompt-file request was logged under a generic "Setup" section instead of its own "Problem 1 — Vibe coder prompts" section, so it was moved under the official problem number and title.

### Prompt 3 (follow-up prompt, later in the assignment)

> sanity check - btw, for prompt file, separate each q/sessions i guess. — [typed during Problem 7]

**What was lacking:** Prompts inside each problem ran together, so every prompt now has its own numbered heading with its role (first, follow-up, additional, sanity check), and sections are separated by dividers.

---

## Problem 2 — Analyze the database

### Prompt 1 (first prompt)

> open up that db file

### Prompt 2 (additional prompt)

> start a harness file, put those tables and fields from that db file there. Record: catalogue matters since the chatbot needs to understand what products do the bookstore provide, the inventory is necessary to check to we have certain size in stock, and users are the people allowed to access, those are the admistrative people

### Prompt 3 (follow-up prompt, sanity check)

> ok, fair enough, sanity check — [screenshots of Problem 2 Panel A and Panel B]

**What was lacking:** The harness file was at the project root instead of `output/harness.md` and only described what each field holds, so it was moved and every field got a short line on why it matters for the shop or chatbot (and "users" was corrected from administrators to shopper accounts).

---

## Problem 3 — Build the Campus Customs website

### Prompt 1 (first prompt)

> ok, P3. lets build the front end. do as the screenshot asks. Get the styling, font etc from the offical bookstore page - https://yalebulldogblue.com/. But draft the home/about us wording part etc in a decent/business way. In your own words. For teh product page, build the catalogue with the pics, info, image etc given in the data folder/catalogue etc.  Lets also make each product a single-item page - with big pic on one side and description/context on the other . Like the amazon style. And when we click the pic on the Product page/catalogue, it should bring us to the individual product page. Besides that, add a floating chatting interface bottom right. No need for talking agent yet. For API, check the last screenshot. Or use the API key I asked you to setup, whichever is easier or cost effective, your call — [screenshots of the nav bar requirement (Home, Products, About Us, Log in, Create account), an Amazon product page as a layout example, and the backend/main.py hint]

### Prompt 2 (follow-up prompt)

> can you make some of the pics soother and better? Some edges looks quite rough — [screenshot of the Baseball Left Chest Crewneck card with jagged edges on a black background]

**What was lacking:** Most product photos were cut-outs on a black background with jagged edges, so a cleanup script smoothed the edges and placed every garment on the site's light-gray background.

### Prompt 3 (sanity check)

> ok, p3 sanity check — [screenshots of Problem 3 Panel A and Panel B]

**What was lacking:** The product cards were missing the short description, and the chat window replied from the browser instead of calling the backend, so a two-line description was added to every card and the chat now sends messages to a stub `POST /api/chat` endpoint.

### Prompt 4 (additional prompt)

> for home can you make it more vivid? like a big hero banner etc? check the Yale bookstore webpage, yale webpage etc, be creatve

**What was lacking:** The first Home page was a plain navy banner with four products, so it was redesigned with a full-width hero, product collage, themed collection tiles, a Yale vs Harvard feature, and category tiles.

---

## Problem 4 — Create account and login

### Prompt 1 (first prompt)

> ok, P4, lets make a normal account creation/login flow. Let's make sure the user can create account and login. New accounts and passwords should be saved to the user table so no hackers (human or AI ) can access

### Prompt 2 (follow-up prompt)

> test that function with this — [screenshot of the seed test user: test@campuscustoms.yale.edu / password, and "confirm you can log in as that user, and that a brand-new account you create also works"]

**What was lacking:** New accounts were hashed with a different number of PBKDF2 rounds than the seed users, so the seed test user couldn't log in until the hashing was matched to the existing 120,000 rounds.

### Prompt 3 (sanity check)

> sanity check for P4 — [screenshots of Problem 4 Panel A and Panel B]

**What was lacking:** The harness explained auth security as a threat table but didn't plainly list what is stored for a user or walk through how passwords are protected, so two dedicated subsections were added, and the section was renamed to the official title "Create account and login".

### Prompt 4 (sanity check, re-run after the Home redesign)

> sanity check for 4? — [screenshots of Problem 4 Panel A and Panel B]

**What was lacking:** Nothing new; after restarting the servers, the seed test user, a brand-new account, password hashing, and the harness sections all re-checked as passing.

---

## Problem 5 — PydanticAI agent backend

### Prompt 1 (first prompt)

> for P5 - lets make the chatbot smarter with pydantic AI agent behind the FastAPI. Let's put the API app in backend/main.py and plug it in with the front-end chat widget. Same as HW3, keep the agent as those four files as screenshot shows-  In main.py, show a chat route so a message from the website returns a reply from the agent. Apply the API key here. Make sure the Agent can help with the request, make it optional that it physically lead teh customer to the page, or showing teh options etc. Let's see how it goes, we might change that function later on.  Put a voice there and safety basics (rule of thumbs, you call first, we can adjust later) in to promptmd.  Update the types in models.py for chat replies/product cards etc. Build an internal feedback and sanity check loop, when things go wrong, check what happened. Or give the customer choice after service for survey like "is this helpful/is this accurate define what you need? etc". In the hardness file, note the way front end talks to FastAPI and how does the agent is loaded. make sure the backend runs as - uvicorn main:app --reload --port 8000 (just make sure it works, not necessarily strictly follow whatever given). Promote cost and run efficiency. — [screenshot of the four agent files: backend/prompts/prompt.md, backend/agent.py, backend/tools.py, backend/models.py]

### Prompt 2 (follow-up prompt)

> show me the frontend, lets see

**What was lacking:** Old sample chats restored from the database showed raw markdown (`**$68**`, `- ` bullets), so the chat bubbles now render bold text and bullet lists safely.

### Prompt 3 (sanity check)

> amazing. Let's do a sanity check — [screenshots of Problem 5 Panel A and Panel B]

**What was lacking:** The harness run instructions didn't show the exact required command, so they now say to activate the .venv and run `uvicorn main:app --reload --port 8000` from `backend/` (verified live), and the section was renamed to the official title "PydanticAI agent backend".

---

## Problem 6 — Tools: product info and stock

### Prompt 1 (first prompt)

> ok P6. I think we cover this already. So just double checking. The prompt wants us to enable the agent tools to lookup real info from our database - campus_customs.db. as the screenshot. Oh but make sure there is no hallucination like inventing prices quantities etc. If there is no items in stock, said "unclear". Meanwhile, expand the prompt, so that agent would know to call the tools for proice and stock qs. Ad or update return types in model.py. in harness, list each tool and explain which model fields for lookup for what and explain why — [screenshot: tools for product description, price, and how many are in stock (by size when the customer asks)]

### Prompt 2 (follow-up prompt, sanity check)

> for the cost, let's try to get rid of the repetitive/unnecessary moves. I am not super concerned. If some others should have higher priority by your judgement, do it. Sanity check — [screenshots of Problem 6 Panel A and Panel B]

**What was lacking:** Greetings and thank-yous still cost model calls, and a slightly wrong product id cost an extra round trip, so small talk now skips the model, near-miss ids resolve automatically, and prompt-cache use is logged (about 88% of input tokens cached).

### Prompt 3 (additional prompt)

> this pic seems broken, fix that or use the old one — [screenshot of the Boola Boola tee with white slivers at the collar and sleeve]

**What was lacking:** The cleaned Boola Boola photo exposed white slivers from its original cut-out, so it is now served as the untouched original via a keep-original list in the cleanup script.

---

## Problem 7 — Chat search that updates the page

### Prompt 1 (first prompt)

> cool, lets move on to P7. again, i think you did it already. The q prompt ask agent to show cards when customer ask about the products. Update prompt and harness for this feature.

### Prompt 2 (follow-up prompt, sanity check)

> sanity check - btw, for prompt file, separate each q/sessions i guess. — [screenshots of Problem 7 Panel A and Panel B]

**What was lacking:** The matching items only appeared as small cards inside the chat bubble, not on the website itself, so the agent's structured matches now also render on the current page as full product cards (image, name, price, short info) in a "Matching items from your chat" section, and each one still opens the single-item page.

---

## Problem 8 — Customer memory

### Prompt 1 (first prompt)

> ok P8.  now we hope to save the chat history in the data base in an decent table and reload it hwen they run. the agent should know who is chatting - name, email, username if log'd in etc. Put that in agent deps and tools that the agent can call upon. Also, let the agent able to read the webpage so when the customer ask like "do you have this one in pink/different size", the agent should understand what does that mean.  Meanwhile, guest can chat whatsoever, but loged in users should have consistent history/memory every time they login. In harness, record how user chat history is stored, what fields the agent see and how page context is passed.

### Prompt 2 (additional prompt)

> when i click create account, please hide this part, only show the account creation part — [screenshot of the "Matching items from your chat: Yale hoodies" section above the page]

**What was lacking:** The chat results section showed on every page, including Log in and Create account, so it is now hidden on those two pages (the results stay saved and reappear on shopping pages).

### Prompt 3 (additional prompt)

> yes plz whatever you need — [reply to my offer to use the original photo for the Basic Hoodie Big Yale, whose right sleeve looked jagged]

**What was lacking:** The Basic Hoodie photo had a jagged sleeve, so it now uses its original; a by-eye review of all 100 cleaned photos found the same white-sliver defect on the Football and Track & Field tees, which also use their originals now, and the home hero collage swapped in the Champion hoodie.

### Prompt 4 (additional prompt)

> when the customer didn't ask in agent, please don't show this — [screenshots of a fresh chat with only the greeting, while the page still showed "Matching items from your chat: Yale hoodies" from an earlier conversation]

**What was lacking:** Page results were kept in the browser even after the chat reset, so a new conversation showed results it never asked for; each result set now records which conversation asked for it (guest or a specific user) and is hidden and cleared when that conversation ends.

### Prompt 5 (additional prompt)

> fix this as well — [screenshot of the Basic Hoodie Big Yale original photo on black, still with a jagged right sleeve]

**What was lacking:** Serving the original photo didn't help because the jagged edge is in the source cut-out itself, so this photo now gets an outline-smoothing step (blur and re-trace the garment edge) and is shown on the light background like the others.

### Prompt 6 (follow-up prompt, sanity check)

> sanity check for P8 - — [screenshots of Problem 8 Panel A and Panel B]

**What was lacking:** Nothing was missing in the work itself (re-checked live: history saved and reloaded in a new session, name and email known from deps, "this in pink?" resolved from the product page, guests chat without stored history), so the section was renamed to the official title "Customer memory".

---

## Problem 9 — Usability improvements

### Prompt 1 (first prompt)

> ok P9, lets make the front end better UI/UX, and better agent. Build a file under output named usability.md.  For our improvement along the way, add them there as well. explain what we add, why it helps.

### Prompt 2 (follow-up prompt, sanity check)

> sanity check - show me the front end after the check — [screenshots of Problem 9 Panel A and Panel B]

**What was lacking:** The rubric asks for 2 front-end and 2 agent/backend improvements, but the work leaned front-end and usability.md didn't label the types, so a new agent tool (`find_similar`) was added and usability.md now opens with a summary table of 2 front-end + 2 agent/backend improvements, each with what we added, why it helps a shopper or the business, and where to see it in the app.

### Prompt 3 (additional prompt)

> we also added the feedback loop right?

**What was lacking:** The feedback loop (automatic answer checks before every reply plus the 👍/👎 survey after it, linked in the run log) was only a short row in Part 2 of usability.md, so it is now a featured agent/backend improvement (A3) with what it does, why it helps, how to find problems with it, and test results.

### Prompt 4 (additional prompt)

> for that agent, give it a anime figure like the bulldog — [screenshot of Handsome Dan bulldog images]

> yup, like a little avatar running or thinking

### Prompt 5 (follow-up prompt)

> pal, that looks like a cat

> hard to tell lol, more or less like a tiger.... — [screenshots of Yale bulldog logos and Handsome Dan photos as references]

> i think that yellow pillow on the right is a good design

**What was lacking:** The first mascot had pointy upright ears (it read as a cat) and the next had brown forehead stripes (it read as a tiger), so it was redrawn as an original round, squishy golden bulldog in the style of the plush pillow: white face, floppy ears, big black nose, a fang, and a navy "Y" belly, with a trotting and thinking animation while the agent works.

---

## Problem 10 — Style the website

### Prompt 1 (first prompt)

> ok P10. We did this already i think. The q prompt asks us to make the website design vivid and creative and then write a design.md file under output and describe what we changed and why it helps customers to stick around and buy. Don't overstate, keep it short.

### Prompt 2 (follow-up prompt, sanity check)

> sanity check — [screenshots of Problem 10 Panel A and Panel B]

**What was lacking:** design.md was grouped by page and didn't mention motion, so it was reorganized into one short table covering the six areas the problem names (fonts, color, hierarchy, motion, product presentation, chat feel), each with concrete changes and why they should help customers stick around and buy.

### Prompt 3 (follow-up prompt, sanity check)

> ok sanity check — [screenshots of Problem 11 Panel A and Panel B]

**What was lacking:** The captions described each screenshot but didn't say plainly what it proved, so every screenshot now has a "Proves:" sentence; links, headings, and double-click opening (no external files) were re-checked.

---

## Problem 12 — Audit trail, safety, finish harness

### Prompt 1 (first prompt)

> ok P12, get an append-only audit_trail.json file of agent loop activities (time, tool name, short args/results, stop reasons). do not wipe it between runs (explain this one to me, what does that mean?) . Also, generate some basic safety rules to give the agent (like no privacy data leak, no abusive words/language etc) and record those in te prompt file. Finish the harness file so it cearly get how te system wiork. make sure to have the following as screen sht - [screenshot of the required harness sections: model fields in models.py and why, tools and abilities, safety rules, specs (loop limits, result caps, models, how to run front + back)]

### Prompt 2 (follow-up prompt, sanity check)

> sanity check — [screenshots of Problem 12 Panel A and Panel B]

**What was lacking:** Nothing in the work itself (audit trail verified as an append-only JSON array with times, tool names, short args/results, and stop reasons that survived a server restart; five safety-rule groups in prompt.md; all four harness sections present), so only the section titles were updated to the official "Audit trail, safety, finish harness".

---

## Problem 13 — Submit: public GitHub repo

### Prompt 1 (first prompt)

> cool, P13 - do you have my github access? — [screenshots of the submission instructions: hw4 folder, public GitHub repo, no .env / campus_customs.db / product images, .env.example with placeholders, expected file layout, local-only data pack, README explaining how to run]

**What was lacking:** There was no README.md yet and the front end still had Vite's boilerplate README, so a project README (layout, placing the data pack, setup, running the back and front end) was written, `.gitignore` was tightened (`.env.*`, `.claude/`), and a dry run confirmed that only code and docs (no secrets, database, or product images) would be published before pushing to the public repo `garychen836/hw4`.

