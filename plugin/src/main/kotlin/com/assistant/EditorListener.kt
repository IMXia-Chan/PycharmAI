package com.assistant

import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.editor.event.EditorFactoryEvent
import com.intellij.openapi.editor.event.EditorFactoryListener
import java.util.concurrent.ConcurrentHashMap

class EditorListener : EditorFactoryListener {
    // 每个编辑器注册的文档监听器,用于在编辑器销毁时解绑,避免监听器对象泄漏
    private val listeners = ConcurrentHashMap<Editor, DocumentListener>()

    override fun editorCreated(event: EditorFactoryEvent) {
        val editor = event.editor
        val project = editor.project ?: return
        val provider = project.getService(LiveIssueHintProvider::class.java)
        val listener = object : DocumentListener {
            override fun documentChanged(e: DocumentEvent) {
                if (!editor.isDisposed) {
                    provider.onDocumentChanged(editor, e.document)
                }
            }
        }
        editor.document.addDocumentListener(listener)
        listeners[editor] = listener
    }

    override fun editorReleased(event: EditorFactoryEvent) {
        val listener = listeners.remove(event.editor) ?: return
        event.editor.document.removeDocumentListener(listener)
    }
}
