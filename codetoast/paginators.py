# -*- coding: utf-8 -*-

import asyncio
import collections
import re

import discord
from discord.ext import commands

from codetoast.hljs import get_language, guess_file_traits

__all__ = (
    "EmojiSettings",
    "PaginatorInterface",
    "PaginatorEmbedInterface",
    "WrappedPaginator",
    "FilePaginator",
)


EmojiSettings = collections.namedtuple("EmojiSettings", "start back forward end close")

EMOJI_DEFAULT = EmojiSettings(
    start="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
    back="\N{BLACK LEFT-POINTING TRIANGLE}",
    forward="\N{BLACK RIGHT-POINTING TRIANGLE}",
    end="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
    close="\N{BLACK SQUARE FOR STOP}",
)


class PaginatorInterface:
    def __init__(self, bot: commands.Bot, paginator: commands.Paginator, **kwargs):
        if not isinstance(paginator, commands.Paginator):
            raise TypeError("paginator must be a commands.Paginator instance")

        self._display_page = 0

        self.bot = bot

        self.message = None
        self.paginator = paginator

        self.owner = kwargs.pop("owner", None)
        self.emojis = kwargs.pop("emoji", EMOJI_DEFAULT)
        self.timeout = kwargs.pop("timeout", 7200)
        self.delete_message = kwargs.pop("delete_message", False)

        self.sent_page_reactions = False

        self.task: asyncio.Task = None
        self.send_lock: asyncio.Event = asyncio.Event()

        self.close_exception: Exception = None

        if self.page_size > self.max_page_size:
            raise ValueError(
                f"Paginator passed has too large of a page size for this interface. "
                f"({self.page_size} > {self.max_page_size})"
            )

    @property
    def pages(self):
        paginator_pages = list(self.paginator._pages)
        if len(self.paginator._current_page) > 1:
            paginator_pages.append(
                "\n".join(self.paginator._current_page)
                + "\n"
                + (self.paginator.suffix or "")
            )
        # pylint: enable=protected-access

        return paginator_pages

    @property
    def page_count(self):
        return len(self.pages)

    @property
    def display_page(self):
        self._display_page = max(0, min(self.page_count - 1, self._display_page))
        return self._display_page

    @display_page.setter
    def display_page(self, value):
        self._display_page = max(0, min(self.page_count - 1, value))

    max_page_size = 2000

    @property
    def page_size(self) -> int:
        page_count = self.page_count
        return self.paginator.max_size + len(f"\nPage {page_count}/{page_count}")

    @property
    def send_kwargs(self) -> dict:
        display_page = self.display_page
        page_num = f"\nPage {display_page + 1}/{self.page_count}"
        content = self.pages[display_page] + page_num
        return {"content": content}

    async def add_line(self, *args, **kwargs):

        display_page = self.display_page
        page_count = self.page_count

        self.paginator.add_line(*args, **kwargs)

        new_page_count = self.page_count

        if display_page + 1 == page_count:
            self._display_page = new_page_count

        self.send_lock.set()

    async def send_to(self, destination: discord.abc.Messageable):

        self.message = await destination.send(**self.send_kwargs)
        await self.message.add_reaction(self.emojis.close)

        self.send_lock.set()

        if self.task:
            self.task.cancel()

        self.task = self.bot.loop.create_task(self.wait_loop())

        if not self.sent_page_reactions and self.page_count > 1:
            await self.send_all_reactions()

        return self

    async def send_all_reactions(self):

        for emoji in filter(None, self.emojis):
            try:
                await self.message.add_reaction(emoji)
            except discord.NotFound:
                break
        self.sent_page_reactions = True

    @property
    def closed(self):
        if not self.task:
            return False
        return self.task.done()

    async def send_lock_delayed(self):
        gathered = await self.send_lock.wait()
        self.send_lock.clear()
        await asyncio.sleep(1)
        return gathered

    async def wait_loop(self):
        start, back, forward, end, close = self.emojis

        def check(payload: discord.RawReactionActionEvent):
            owner_check = not self.owner or payload.user_id == self.owner.id

            emoji = payload.emoji
            if isinstance(emoji, discord.PartialEmoji) and emoji.is_unicode_emoji():
                emoji = emoji.name

            tests = (
                owner_check,
                payload.message_id == self.message.id,
                emoji,
                emoji in self.emojis,
                payload.user_id != self.bot.user.id,
            )

            return all(tests)

        task_list = [
            self.bot.loop.create_task(coro)
            for coro in {
                self.bot.wait_for("raw_reaction_add", check=check),
                self.bot.wait_for("raw_reaction_remove", check=check),
                self.send_lock_delayed(),
            }
        ]

        try:
            last_kwargs = None

            while not self.bot.is_closed():
                done, _ = await asyncio.wait(
                    task_list, timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED
                )

                if not done:
                    raise asyncio.TimeoutError

                for task in done:
                    task_list.remove(task)
                    payload = task.result()

                    if isinstance(payload, discord.RawReactionActionEvent):
                        emoji = payload.emoji
                        if (
                            isinstance(emoji, discord.PartialEmoji)
                            and emoji.is_unicode_emoji()
                        ):
                            emoji = emoji.name

                        if emoji == close:
                            await self.message.delete()
                            return

                        if emoji == start:
                            self._display_page = 0
                        elif emoji == end:
                            self._display_page = self.page_count - 1
                        elif emoji == back:
                            self._display_page -= 1
                        elif emoji == forward:
                            self._display_page += 1

                        if payload.event_type == "REACTION_ADD":
                            task_list.append(
                                self.bot.loop.create_task(
                                    self.bot.wait_for("raw_reaction_add", check=check)
                                )
                            )
                        elif payload.event_type == "REACTION_REMOVE":
                            task_list.append(
                                self.bot.loop.create_task(
                                    self.bot.wait_for(
                                        "raw_reaction_remove", check=check
                                    )
                                )
                            )
                    else:
                        task_list.append(
                            self.bot.loop.create_task(self.send_lock_delayed())
                        )

                if not self.sent_page_reactions and self.page_count > 1:
                    self.bot.loop.create_task(self.send_all_reactions())
                    self.sent_page_reactions = True

                if self.send_kwargs != last_kwargs:
                    try:
                        await self.message.edit(**self.send_kwargs)
                    except discord.NotFound:
                        return

                    last_kwargs = self.send_kwargs

        except (asyncio.CancelledError, asyncio.TimeoutError) as exception:
            self.close_exception = exception

            if self.bot.is_closed():
                return

            if self.delete_message:
                return await self.message.delete()

            for emoji in filter(None, self.emojis):
                try:
                    await self.message.remove_reaction(emoji, self.bot.user)
                except (discord.Forbidden, discord.NotFound):
                    pass

        finally:
            for task in task_list:
                task.cancel()


class PaginatorEmbedInterface(PaginatorInterface):
    def __init__(self, *args, **kwargs):
        self._embed = kwargs.pop("embed", None) or discord.Embed()
        super().__init__(*args, **kwargs)

    @property
    def send_kwargs(self) -> dict:
        display_page = self.display_page
        self._embed.description = self.pages[display_page]
        self._embed.set_footer(text=f"Page `{display_page + 1}`/**{self.page_count}**")
        return {"embed": self._embed}

    max_page_size = 2048

    @property
    def page_size(self) -> int:
        return self.paginator.max_size


class WrappedPaginator(commands.Paginator):
    def __init__(
        self,
        *args,
        wrap_on=("\n", " "),
        include_wrapped=True,
        force_wrap=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.wrap_on = wrap_on
        self.include_wrapped = include_wrapped
        self.force_wrap = force_wrap

    def add_line(self, line="", *, empty=False):
        true_max_size = self.max_size - self._prefix_len - self._suffix_len - 2
        original_length = len(line)

        while len(line) > true_max_size:
            search_string = line[0 : true_max_size - 1]
            wrapped = False

            for delimiter in self.wrap_on:
                position = search_string.rfind(delimiter)

                if position > 0:
                    super().add_line(line[0:position], empty=empty)
                    wrapped = True

                    if self.include_wrapped:
                        line = line[position:]
                    else:
                        line = line[position + len(delimiter) :]

                    break

            if not wrapped:
                if self.force_wrap:
                    super().add_line(line[0 : true_max_size - 1])
                    line = line[true_max_size - 1 :]
                else:
                    raise ValueError(
                        f"Line of length `{original_length}` had sequence of `{len(line)}` characters"
                        f" (max is {true_max_size}) that WrappedPaginator could not wrap with"
                        f" delimiters: `{self.wrap_on}`"
                    )

        super().add_line(line, empty=empty)


class FilePaginator(commands.Paginator):
    __encoding_regex = re.compile(br"coding[=:]\s*([-\w.]+)")

    def __init__(self, fp, line_span=None, language_hints=(), **kwargs):
        language = ""

        for hint in language_hints:
            language = get_language(hint)

            if language:
                break

        if not language:
            try:
                language = get_language(fp.name)
            except AttributeError:
                pass

        content, _, file_language = guess_file_traits(fp.read())

        language = file_language or language
        lines = content.split("\n")

        super().__init__(prefix=f"```{language}", suffix="```", **kwargs)

        if line_span:
            line_span = sorted(line_span)

            if min(line_span) < 1 or max(line_span) > len(lines):
                raise ValueError("Linespan goes out of bounds.")

            lines = lines[line_span[0] - 1 : line_span[1]]

        for line in lines:
            self.add_line(line)


class WrappedFilePaginator(FilePaginator, WrappedPaginator):
    """
    CodeToast WrappedFilePaginator
    """
