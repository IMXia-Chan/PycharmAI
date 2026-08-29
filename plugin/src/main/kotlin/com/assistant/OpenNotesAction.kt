package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

/** 学习笔记:用浏览器打开后端 /web#notes 页面(笔记 + 错误记录 + 生成笔记)。 */
class OpenNotesAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                project,
                "后端未启动,网页打不开。\n请先在项目目录运行:`python -m backend.main`",
                "学习笔记",
            )
            return
        }
        BrowserUtil.open(AssistantSettings.getInstance().state.backendUrl.trimEnd('/') + "/web#notes")
    }
}
