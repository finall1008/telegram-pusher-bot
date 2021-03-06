# 如何使用？

## 新版本带来的工作流变化

从此版本开始，我们将监视器由频道切换到群组。好处是显而易见的：

- 可以使用 `CommandHandler`，避免不规范的命令处理实现。
- 可以获取回复消息，从而实现自定义标签功能。
- ……

但是这带来了唯一的问题，即，我们会遇到 Telegram 官方对于 Bot 不能读取其他 Bot 消息的限制。这个限制目前在频道中不存在，因此此前的版本不会受其影响。

要规避这一影响，只需新建一个**中继频道**，在里面添加消息来源 Bot 和本 Bot ，并设置从中继频道到监视器群组的自动转发规则即可。

另请注意，Bot 不能编辑直接由您发送的消息，所以直接由您发送的消息将无法加上控制按钮。如果您要手动为 Bot 提供消息，请也发在中继频道中。

## 主按钮页

在监视器**群组**（即 Bot 监控其中的消息，并为其加上功能按钮供使用的群组）中，每条消息底部都会带有一个“加入队列“按钮，除非它来自本 Bot 或是一条指令，如图。

![主按钮页（未加入队列）](../images/main_buttons_outside.png)

点按即可将这条消息的链接内容加入推送队列。注意：链接之外的内容会被无视，且只会处理其中的第一条链接。按钮会自动变化为如图：

![主按钮页（已加入队列）](../images/main_buttons_inside.png)

- ”移出队列“：将这条消息的内容移出推送队列。
- ”标签“：为这条消息指定推送时要附带的标签。按钮将变为标签按钮页。
- ”目标“：为这条消息指定需要推送到的目标。按钮将变为目标按钮页。
  - 如果您不指定任何目标，消息会被推送至默认目标，即配置文件中 `"targets"` 数组的第一个。
  - 如果您在使用 `/push` 指令推送时指定了目标，则这里选择的目标将不生效。
- ”推送“：立即推送这条消息。

## 标签按钮页

标签按钮页如图。

![标签按钮页](../images/tag_buttons.png)

- 标签按钮：为这条消息指定推送时要附带的标签。已选择的标签旁边将有 ”[✓]“。
- 自定义：添加自定义标签。按下后， Bot 会要求您在 15 秒内回复自定义标签。回复成功后，这个标签将会被添加为标签按钮。若回复超时，则会退出自定义标签状态，您可以继续发送指令。
- ”目标“：切换到目标按钮页。
- ”返回“：回到主按钮页。

## 目标按钮页

目标按钮页如图。各按钮的行为都与标签按钮页同理。

![目标按钮页](../images/target_buttons.png)

## 指令

- `/push`：立即推送队列中的所有内容。
    - 推送时可以用如下形式指定目标和标签。队列中的消息将被**额外**推送到指定的目标；指定的目标应为用户名，**且开头应有@**，否则将作为tag处理；队列中的消息将全部被**额外附加上**指定的标签：
```
/push @a_group a_tag @a_channel another_tag one_more_tag ...
```
- `/check`：检查当前推送队列中的内容。
- `/log_by_id`：将当前监视器改为用 ID 形式在配置文件中记录。
  - 原来记录的监视器用户名将被删除。
  - 由于私有频道/群组没有用户名，只有在执行过此操作后，您才可以将监视器转为私有。之后您也可以重新改为公开，而无需执行任何操作。
- `/start`：用来叫醒 Bot, 实际上并没有什么用处。
- `/restart`：远程重启 Bot 。
- `/commands`：列出所有可用指令，需注意列出的选项在当前的环境内不一定可用。
