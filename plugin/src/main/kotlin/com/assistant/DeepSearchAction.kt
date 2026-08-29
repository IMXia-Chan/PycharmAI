package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

/** 网页端 AI 深度搜索(快捷键 Ctrl+Alt+A):用浏览器打开后端 /web 工作台。
 *  一个入口包含:AI 问答、中文搜函数、学习笔记(按文件分组 + 导出 PDF)、函数对比。 */
class DeepSearchAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                project,
                "后端未启动,网页打不开。\n请先在项目目录运行:`python -m backend.main`",
                "网页端 AI 深度搜索",
            )
            return
        }
        val token = BackendClient.openWeb()
        if (token.isBlank()) {
            Messages.showWarningDialog(project, "网页入口令牌获取失败,请稍后重试。", "网页端 AI 深度搜索")
            return
        }
        BrowserUtil.open(AssistantSettings.getInstance().state.backendUrl.trimEnd('/') + "/web?token=" + token)
    }
}
