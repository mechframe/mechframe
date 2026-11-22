"""What other modules may call, and only those that list `embeds` under
requires.modules: the same reading of a link the site draws its players from,
for a place that can't hold a player, such as `campaigns`' emails, which show
a card with "Watch on YouTube" or "Listen on Spotify" instead.
"""

from embeds.providers import Embed, recognise, words_for

__all__ = ["Embed", "recognise", "words_for"]
