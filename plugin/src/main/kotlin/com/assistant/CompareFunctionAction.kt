package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

/** 对比函数/指令(快捷键 Ctrl+Alt+F):用浏览器打开后端 /web#compare 页面。 */
class CompareFunctionAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                project,
                "后端未启动,网页打不开。\n请先在项目目录运行:`python -m backend.main`",
                "函数对比",
            )
            return
        }
        BrowserUtil.open(AssistantSettings.getInstance().state.backendUrl.trimEnd('/') + "/web#compare")
    }
}
