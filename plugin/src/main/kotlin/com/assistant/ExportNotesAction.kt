package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import java.io.File
import javax.swing.JFileChooser

/** 把积累的 AI 笔记一键导出成 Markdown 文件。 */
class ExportNotesAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "读取笔记…", false) {
            override fun run(indicator: ProgressIndicator) {
                val notes = try {
                    BackendClient.notes()
                } catch (ex: Exception) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showErrorDialog(project, ex.message ?: "读取失败,请确认后端已启动", "错误")
                    }
                    return
                }
                if (notes.isEmpty()) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showInfoMessage(project, "还没有笔记可导出。", "笔记导出")
                    }
                    return
                }
                val md = buildMarkdown(notes)
                ApplicationManager.getApplication().invokeLater { chooseAndSave(project, md) }
            }
        })
    }

    private fun buildMarkdown(notes: List<Note>): String {
        val sb = StringBuilder()
        sb.append("# Python 学习笔记\n\n")
        for (n in notes) {
            if (n.title.isNotBlank()) sb.append("## ").append(n.title).append("\n\n")
            sb.append(n.content).append("\n\n---\n\n")
        }
        return sb.toString()
    }

    private fun chooseAndSave(project: Project, content: String) {
        val chooser = JFileChooser().apply {
            dialogTitle = "导出笔记为 Markdown"
            selectedFile = File("AI学习笔记.md")
        }
        if (chooser.showSaveDialog(null) != JFileChooser.APPROVE_OPTION) return
        val picked = chooser.selectedFile ?: return
        val target = if (picked.name.endsWith(".md", ignoreCase = true)) picked else File(picked.absolutePath + ".md")
        try {
            target.writeText(content, Charsets.UTF_8)
            Messages.showInfoMessage(project, "已导出到:\n${target.absolutePath}", "笔记导出")
        } catch (ex: Exception) {
            Messages.showErrorDialog(project, "写入失败:${ex.message}", "错误")
        }
    }
}
