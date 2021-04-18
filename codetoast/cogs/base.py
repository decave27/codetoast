# -*- coding: utf-8 -*-

import asyncio
import collections
import contextlib
import datetime
import typing

from discord.ext import commands

CommandTask = collections.namedtuple("CommandTask", "index ctx task")


class BaseCog(commands.Cog):
    class ToastCommand:
        def __init__(self, prefix: str = None, standalone_ok: bool = False, **kwargs):
            self.parent: typing.Union[str, BaseCog.ToastCommand] = prefix
            self.standalone_ok = standalone_ok
            self.kwargs = kwargs
            self.callback = None
            self.depth: int = 0
            self.has_children: bool = False

        def __call__(self, callback: typing.Callable):
            self.callback = callback
            return self

    load_time = datetime.datetime.now()

    def __init__(self, *args, **kwargs):
        self.bot: commands.Bot = kwargs.pop("bot")
        self.start_time: datetime.datetime = datetime.datetime.now()
        self.tasks = collections.deque()
        self.task_count: int = 0

        command_lookup = {}

        for kls in reversed(type(self).__mro__):
            for key, cmd in kls.__dict__.items():
                if isinstance(cmd, BaseCog.ToastCommand):
                    command_lookup[key] = cmd

        command_set = list(command_lookup.items())

        for key, cmd in command_set:
            if cmd.parent and isinstance(cmd.parent, str):
                if cmd.standalone_ok:
                    cmd.parent = command_lookup.get(cmd.parent, None)
                else:
                    try:
                        cmd.parent = command_lookup[cmd.parent]
                    except KeyError as exception:
                        raise RuntimeError(
                            f"Couldn't associate BaseCog command {key} with its parent {cmd.parent}"
                        ) from exception
            if cmd.callback is None:
                raise RuntimeError(f"BaseCog command {key} lacks callback")

        for key, cmd in command_set:
            parent = cmd.parent
            while parent:
                parent.has_children = True
                cmd.depth += 1
                parent = parent.parent

        command_set.sort(key=lambda c: c[1].depth)
        association_map = {}

        self.feature_commands = {}

        for key, cmd in command_set:
            if cmd.parent:
                parent = association_map[cmd.parent]
                command_type = parent.group if cmd.has_children else parent.command
            else:
                command_type = commands.group if cmd.has_children else commands.command

            association_map[cmd] = target_cmd = command_type(**cmd.kwargs)(cmd.callback)
            target_cmd.cog = self
            self.feature_commands[key] = target_cmd
            setattr(self, key, target_cmd)

        self.__cog_commands__ = (*self.__cog_commands__, *self.feature_commands.values())

        super().__init__(*args, **kwargs)

    async def cog_check(self, ctx: commands.Context):
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner("You must own this bot to use CodeToast")
        return True

    @contextlib.contextmanager
    def submit(self, ctx: commands.Context):
        self.task_count += 1

        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None

        cmdtask = CommandTask(self.task_count, ctx, current_task)

        self.tasks.append(cmdtask)

        try:
            yield cmdtask
        finally:
            if cmdtask in self.tasks:
                self.tasks.remove(cmdtask)
