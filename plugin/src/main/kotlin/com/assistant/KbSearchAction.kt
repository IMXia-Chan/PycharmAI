package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.ui.Messages
import kotlin.math.round

/** 搜索本地知识库(公共 + 个人),弹窗展示命中结果。 */
class KbSearchAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val query = Messages.showInputDialog(
            project,
            "输入报错关键词(如 requests / TypeError):",
            "知识库搜索",
            null,
        )?.trim()
        if (query.isNullOrBlank()) return

        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "搜索知识库…", false) {
            override fun run(indicator: ProgressIndicator) {
                val text = try {
                    val (pub, prv) = BackendClient.searchKbAll(query)
                    format(pub, prv)
                } catch (ex: Exception) {
                    "搜索失败:${ex.message ?: "请确认后端已启动"}"
                }
                ApplicationManager.getApplication().invokeLater {
                    AiResultDialog(project, "知识库搜索结果", text).show()
                }
            }
        })
    }

    private fun format(pub: List<KbHit>, prv: List<KbHit>): String {
        val total = pub.size + prv.size
        if (total == 0) return "没有找到相关记录。"
        val sb = StringBuilder("共 $total 条命中\n\n")
        appendHits(sb, "公共库", pub)
        appendHits(sb, "个人库", prv)
        return sb.toString().trimEnd()
    }

    private fun appendHits(sb: StringBuilder, label: String, hits: List<KbHit>) {
        if (hits.isEmpty()) return
        sb.append("── ").append(label).append(" ──\n")
        hits.forEachIndexed { i, h ->
            sb.append("\n[").append(i + 1).append("] ")
            sb.append(h.errorType.ifBlank { "未知错误" })
            if (h.language.isNotBlank()) sb.append(" · ").append(h.language)
            sb.append(" · 相关度 ").append(round(h.score * 100) / 100.0).append("\n")
            if (h.errorMessage.isNotBlank()) sb.append("报错: ").append(h.errorMessage).append("\n")
            if (h.solution.isNotBlank()) sb.append("解决: ").append(h.solution).append("\n")
            val src = if (h.isPrivate) h.filePath else h.source
            if (src.isNotBlank()) sb.append("来源: ").append(src).append("\n")
            if (h.tags.isNotBlank()) sb.append("标签: ").append(h.tags).append("\n")
        }
        sb.append("\n")
    }
}
