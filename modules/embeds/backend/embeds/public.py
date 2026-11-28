"""What other modules may call, and only those that list `embeds` under
requires.modules: the same reading of a link the site draws its players from,
for a place that can't hold a player, such as `campaigns`' emails, which show
a card with "Watch on YouTube" or "Listen on Spotify" instead; and the
reading of Bandcamp's own embed code (0.1.2), for a module that keeps a
Bandcamp player from what an admin pasted, such as `discography`.
"""

from embeds.providers import Embed, from_bandcamp_code, recognise, words_for

__all__ = ["Embed", "from_bandcamp_code", "recognise", "words_for"]
