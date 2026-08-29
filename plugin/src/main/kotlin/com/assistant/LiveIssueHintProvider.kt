package com.assistant

import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.EditorCustomElementRenderer
import com.intellij.openapi.editor.Inlay
import com.intellij.openapi.editor.markup.TextAttributes
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.TextRange
import com.intellij.ui.JBColor
import java.awt.Graphics
import java.awt.Graphics2D
import java.awt.Rectangle
import java.awt.geom.Rectangle2D
import java.util.concurrent.Executors
import kotlin.math.abs

/**
 * 输入时实时检测代码,并通过 Inlay 在问题行尾内联提示常见错误。
 * 现在会发送整个文件 + 当前行号,让后端(AI)能发现跨行问题(如变量未定义)。
 */
@Service(Service.Level.PROJECT)
class LiveIssueHintProvider(private val project: Project) : Disposable {

    private val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "python-assistant-hints") }

    @Volatile
    private var generation = 0L

    fun onDocumentChanged(editor: Editor, document: Document) {
        val file = FileDocumentManager.getInstance().getFile(document) ?: return
        if (file.extension?.lowercase() != "py") return

        val current = ++generation
        val line0 = document.getLineNumber(editor.caretModel.offset)  // 0-based
        val line1 = line0 + 1                                          // 1-based,发后端
        val fullCode = document.text
        val lineText = document.getText(
            TextRange.create(document.getLineStartOffset(line0), document.getLineEndOffset(line0))
        ).trim()

        if (lineText.isEmpty()) {
            clearHints(editor)
            return
        }

        executor.submit {
            try {
                Thread.sleep(1200)
            } catch (_: InterruptedException) {
                return@submit
            }
            if (current != generation) return@submit
            val issues = try {
                BackendClient.analyze(fullCode, line1)
            } catch (_: Exception) {
                emptyList()
            }
            if (current != generation) return@submit
            ApplicationManager.getApplication().invokeLater {
                if (current != generation || editor.isDisposed) return@invokeLater
                renderHints(editor, line1, issues)
            }
        }
    }

    private fun clearHints(editor: Editor) {
        ApplicationManager.getApplication().invokeLater {
            if (!editor.isDisposed) disposeHints(editor)
        }
    }

    private fun disposeHints(editor: Editor) {
        editor.inlayModel.getAfterLineEndElementsInRange(0, editor.document.textLength).forEach { it.dispose() }
    }

    private fun renderHints(editor: Editor, currentLine: Int, issues: List<Issue>) {
        if (editor.isDisposed) return
        disposeHints(editor)
        if (issues.isEmpty()) return
        val doc = editor.document
        // 优先展示当前行及其附近的 issue
        val sorted = issues.sortedBy { if (it.line <= 0) 0 else abs(it.line - currentLine) }
        sorted.take(3).forEach { issue ->
            val lineNo = if (issue.line > 0) issue.line - 1 else currentLine - 1  // 转 0-based
            if (lineNo < 0 || lineNo >= doc.lineCount) return@forEach
            val text = buildString {
                append("⚠ ")
                append((issue.title.ifBlank { issue.message }).take(40))
                if (issue.suggestion.isNotBlank()) append("  →  ").append(issue.suggestion.take(40))
            }
            try {
                editor.inlayModel.addAfterLineEndElement(
                    doc.getLineEndOffset(lineNo), false, TextInlayRenderer(text)
                )
            } catch (_: Exception) {
                // 忽略单条渲染失败
            }
        }
    }

    override fun dispose() {
        executor.shutdownNow()
    }
}

private class TextInlayRenderer(private val text: String) : EditorCustomElementRenderer {
    override fun calcWidthInPixels(inlay: Inlay<*>): Int {
        val fm = inlay.editor.contentComponent.getFontMetrics(inlay.editor.contentComponent.font)
        return fm.stringWidth(text) + 12
    }

    override fun paint(inlay: Inlay<*>, g: Graphics, targetRegion: Rectangle, textAttributes: TextAttributes) {
        val fm = inlay.editor.contentComponent.getFontMetrics(inlay.editor.contentComponent.font)
        g.color = JBColor.GRAY
        g.drawString(text, targetRegion.x + 4, targetRegion.y + fm.ascent)
    }

    override fun paint(inlay: Inlay<*>, g: Graphics2D, targetRegion: Rectangle2D, textAttributes: TextAttributes) {
        val fm = inlay.editor.contentComponent.getFontMetrics(inlay.editor.contentComponent.font)
        g.color = JBColor.GRAY
        g.drawString(text, (targetRegion.x + 4).toFloat(), (targetRegion.y + fm.ascent).toFloat())
    }
}
