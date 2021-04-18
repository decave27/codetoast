import io
import os
import re

import aiohttp
from discord.ext import commands

from codetoast.cogs.base import BaseCog
from codetoast.hljs import get_language, guess_file_traits
from codetoast.paginators import PaginatorInterface, WrappedFilePaginator


class FileSystem(BaseCog):
    __cat_line_regex = re.compile(r"(?:\.\/+)?(.+?)(?:#L?(\d+)(?:\-L?(\d+))?)?$")

    @BaseCog.ToastCommand(prefix="toast", name="cat")
    async def toast_cat(self, ctx: commands.Context, argument: str):
        match = self.__cat_line_regex.search(argument)

        if not match:
            return await ctx.send("Couldn't parse this input.")

        path = match.group(1)

        line_span = None

        if match.group(2):
            start = int(match.group(2))
            line_span = (start, int(match.group(3) or start))

        if not os.path.exists(path) or os.path.isdir(path):
            return await ctx.send(f"`{path}`: The file could not be found")

        size = os.path.getsize(path)

        if size <= 0:
            return await ctx.send(
                f"`{path}`: Cowardly refusing to read a file with no size stat"
                f" (it may be empty, endless or inaccessible)."
            )

        if size > 50 * (1024 ** 2):
            return await ctx.send(f"`{path}`: Cowardly refusing to read a file >50MB.")

        try:
            with open(path, "rb") as file:
                data = file.read()
                await ctx.send(f"`{str(path)}`", file=discord.File(str(path)))

        except UnicodeDecodeError:
            return await ctx.send(
                f"`{path}`: Couldn't determine the encoding of this file."
            )

        except ValueError as exc:
            error_string = io.StringIO(str(exe))
            return await ctx.send(
                f"`{path}`: Couldn't read this file",
                file=discord.File(fp=error_string, filename="error.txt"),
            )

    @BaseCog.ToastCommand(prefix="toast", name="curl")
    async def toast_curl(self, ctx: commands.Context, url: str):
        url = url.lstrip("<").rstrip(">")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.read()
                hints = (response.content_type, url)
                code = response.status

            if not data:
                return await ctx.send(f"HTTP response was empty (status code {code}).")

            filesize_threshold = (
                ctx.guild.filesize_limit if ctx.guild else 8 * 1024 * 1024
            ) - 1024

            if len(data) < filesize_threshold:
                language = None

                for hint in hints:
                    language = get_language(hint)

                    if language:
                        break

                await ctx.send(
                    file=discord.File(
                        filename=f"response.{language or 'txt'}", fp=io.BytesIO(data)
                    )
                )
            else:
                try:
                    paginator = WrappedFilePaginator(
                        io.BytesIO(data), language_hints=hints, max_size=1985
                    )
                except UnicodeDecodeError:
                    return await ctx.send(
                        f"Couldn't determine the encoding of the response. (status code {code})"
                    )
                except ValueError as exc:
                    return await ctx.send(
                        f"Couldn't read response (status code {code}), {exc}"
                    )

                interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                await interface.send_to(ctx)
