package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

/** 打开「AI 问答」网页(快捷键 Ctrl+Alt+Q):用浏览器打开后端 /web 页面,替代原生窗口。 */
class OpenChatAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                project,
                "后端未启动,网页打不开。\n请先在项目目录运行:`python -m backend.main`",
                "AI 问答",
            )
            return
        }
        BrowserUtil.open(AssistantSettings.getInstance().state.backendUrl.trimEnd('/') + "/web#chat")
    }
}
