package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

/** 中文搜函数/指令:用浏览器打开后端 /web#search 页面,替代原生弹窗 + Edge 跳转。 */
class SearchFunctionAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                project,
                "后端未启动,网页打不开。\n请先在项目目录运行:`python -m backend.main`",
                "中文搜索",
            )
            return
        }
        BrowserUtil.open(AssistantSettings.getInstance().state.backendUrl.trimEnd('/') + "/web#search")
    }
}
