# 关于为本项目添加新模块的说明

子模块被放在以下位置：

## [`utils`](utils/__init__.py)

垃圾桶, 把没有太大依赖关系而且要在别的模块中访问的东西丢进去. 注意将独立模块作为 [`utils`](utils/__init__.py) 的子模块引入而将单独的函数/类定义等放在 [`utils/__init__.py`](utils/__init__.py) 当中.

## [`commands`](commands/__init__.py)

放所有的命令. 每个命令作为一个子模块放在其中, 在 bot 运行时会被自动加载. 注意每个命令:

* 需要有一个 `register(update: Updater)` 方法, 对 updater 的操作在这个函数内完成.
* 需要有一个 `describe() -> str` 方法, 用来生成描述用的字符串. (大多数情况下直接 `return` 描述就完事了)
* 需要有一个 `run(*args, **kwargs)` 方法, 作为命令被(以诡异方式, 待实现)调用时的实际入口函数.
* 注意模块的名称即为命令的名称.
* 可以写成子 package.
