# 0067: Social posting, any module's content shared through Buffer

- **Status:** Decided. The owner approved `dev plans/contracts/social.md` as recommended on 2026-11-24, its five questions answered as recommended, after answering `blog.md` §8, 7 the same day. Applied in its PR.
- **Context:**
  - The owner wants VybeSite's social posting: a published post sent to the company's channels through Buffer, the one integration that reaches LinkedIn pages without LinkedIn's app review. It's to be a module of its own, "any module shares through", blog first, then releases and products (`blog.md` §8, 7).
  - Modules never import each other except through a `public.py` listed in `requires.modules` (SPEC 7). Listing social there would make it a must for blog, and listing blog would tie social to one module. Neither is wanted: a site without social still has a blog.
  - VybeSite kept the Buffer key in Settings only. The owner asked for the host or Settings, as the AI's key is (decision 0058).
- **Decision:**
  1. **The thing is named by its content type and id** (`blog.post`, the hooks' key), never by a module's rows. The kernel resolves it: `server_copy.preview(db, type, id)` takes the path from the type's search source (`search.public_document`, read from the source's rows and only while the public may see it), then the description and image from the page the server copy answers at that path, the site's social card when it has none. The title is the thing's own, as search shows it: the page's `<title>` may add the site's name. So anything public that site search finds can be shared, with no code of the sharing module's beyond drawing the card.
  2. **A props slot, `content.share`,** drawn by the kit's `<ShareParts type id live />`. Social fills it with its Share card, for `social.post.send`. Blog's post editor draws it after After publishing. A page draws nothing there while no module on fills it. Like the text slots (decision 0060), its parts are given props and are never a `SlotOutlet`'s.
  3. **Shares are by hand** (§8, 1): someone picks the channels Buffer reaches, edits one text, and chooses Buffer's queue, now, a set time or a draft in Buffer. Nothing is posted by itself when something publishes.
  4. **A share is stored before it's sent,** as VybeSite's is. Each channel's share is committed as `sending` under a transaction-scoped advisory lock on the thing, so two presses can't both pass the check, then the channels' calls go at once. One whose request went out with no answer back is `unknown` and counts as shared, so nothing is posted twice by mistake. The calls run in the request, as `kernel.ai`'s do: the person waits for the answer, at most 15 seconds a channel, all at once.
  5. **The token** is `BUFFER_ACCESS_TOKEN` on the host or `buffer_token` in the settings section `social`, sealed by the kernel's settings; the saved one wins, and one that can't be opened is reported, never swapped for the host's (decision 0058's order). Check the token keeps the channels Buffer lists, so a Share card opens with no call to Buffer. A change to the section forgets them (`kernel.settings.changed`).
  6. **Link posts only,** to LinkedIn, Facebook, X, Threads, Bluesky and Mastodon (§8, 4). A channel elsewhere is listed with why it can't take one.
- **Rejected:**
  - **An event social hears** (`blog.post.published`, as campaigns does): it suits a post sent by itself on publishing, not a person choosing channels, words and a time, and a release or a product would each need an event of its own.
  - **Blog listing social in `requires.modules`** and importing its `public.ts`: a blog would need social.
  - **Social reading each module's rows** through their `public.py`: every new module would need code in social.
  - **Sending through a job:** a retried job can't tell whether its first try posted; the record-first send in the request can, and the person sees the result at once.
- **Consequences:**
  - SPEC 6 gains `server_copy.preview`, `server_copy.Preview` and `search.public_document`; SPEC 8 the slot `content.share` and `ShareParts`; `schema/module.schema.json` the slot's name.
  - Discography's releases and products get their Share card with one `ShareParts` line on their admin pages, once their types are searched.
  - No suite calls Buffer: `harness/fake_buffer.py` answers the test app's and the unit tests' calls, the site's own address check included.
  - A site takes it with `mechframe add social`, and the kernel's part with `mechframe upgrade kernel`.
