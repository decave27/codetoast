# -*- coding: utf-8 -*-

from discord.ext import commands
from codetoast.cogs.base import BaseCog
from codetoast.metadata import __version__
from codetoast.utils import package_version
from codetoast.paginators import PaginatorInterface
import humanize
import sys

try:
    import psutil
except ImportError:
    psutil = None


class Main(BaseCog):
    @BaseCog.ToastCommand(
        name="codetoast",
        aliases=["ct"],
        invoke_without_command=True,
        ignore_extra=False,
        hidden=True,
    )
    async def toast(self, ctx: commands.Context):
        import_modules = [
            sys.modules[name] for name in set(sys.modules) & set(globals())
        ]
        summary = [
            f"🍞 CodeToast`(v{__version__})`, 🛠️ Debugging module for discord.py 🤖 bots\n",
            f"discord.py`(v{package_version('discord.py')})` `{str(self.bot.user)}` bot, ",
            f"Python `{sys.version}` on `{sys.platform}`",
            f"🗃️ {len(import_modules)} Modules was loaded {humanize.naturaltime(self.load_time)}, "
            f"🔌 {len(self.bot.cogs)} cog was loaded {humanize.naturaltime(self.start_time)}.",
        ]
        if psutil:

            try:
                proc = psutil.Process()
                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        summary.append(
                            f"Using `{humanize.naturalsize(mem.rss)}` physical memory and "
                            f"`{humanize.naturalsize(mem.vms)}` virtual memory, "
                            f"`{humanize.naturalsize(mem.uss)}` of which unique to this process."
                        )
                    except psutil.AccessDenied:
                        pass
                    try:
                        name = proc.name()
                        pid = proc.pid
                        thread_count = proc.num_threads()

                        summary.append(
                            f"💽 Running on PID {pid} (`{name}`) with {thread_count} thread(s)."
                        )
                    except psutil.AccessDenied:
                        pass

                    summary.append("")
            except psutil.AccessDenied:
                summary.append(
                    "❌ System information could not be loaded because the psutil module could not be accessed"
                )
                summary.append("")

        cache_summary = (
            f"🚪 {len(self.bot.guilds)} guild(s) and 😁 {len(self.bot.users)} user(s)"
        )

        if isinstance(self.bot, discord.AutoShardedClient):
            summary.append(
                f"`💡 {str(self.bot.user)}` is automatically sharded and can see {cache_summary}."
            )
        elif self.bot.shard_count:
            summary.append(
                f"`💡 {str(self.bot.user)}` is manually sharded and can see {cache_summary}."
            )
        else:
            summary.append(
                f"`💡 {str(self.bot.user)}` is not sharded and can see {cache_summary}."
            )
        summary.append(
            f"🎚️ Average websocket latency: {round(self.bot.latency * 1000, 2)}ms"
        )

        await ctx.send("\n".join(summary))
