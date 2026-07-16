import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { PlainTextPlugin } from "@lexical/react/LexicalPlainTextPlugin";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { ClearEditorPlugin } from "@lexical/react/LexicalClearEditorPlugin";
import { AutoFocusPlugin } from "@lexical/react/LexicalAutoFocusPlugin";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import {
  $getRoot,
  CLEAR_EDITOR_COMMAND,
  COMMAND_PRIORITY_HIGH,
  KEY_ENTER_COMMAND,
  type EditorState,
  type LexicalEditor,
} from "lexical";

import { cn } from "./ui/utils";

export interface RichTextInputHandle {
  clear: () => void;
  focus: () => void;
}

interface RichTextInputProps {
  /** Fires with the plain-text content on every edit. */
  onChange?: (text: string) => void;
  /** Fires on Enter (Shift+Enter inserts a newline instead). */
  onSubmit?: () => void;
  placeholder?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  className?: string;
  ariaLabel?: string;
}

/** Capture the editor instance so the parent ref can clear/focus it. */
function EditorRefPlugin({ editorRef }: { editorRef: React.MutableRefObject<LexicalEditor | null> }) {
  const [editor] = useLexicalComposerContext();
  editorRef.current = editor;
  return null;
}

/** Enter submits; Shift+Enter falls through to the default newline. */
function EnterSubmitPlugin({ onSubmit }: { onSubmit?: () => void }) {
  const [editor] = useLexicalComposerContext();
  useEffect(
    () =>
      editor.registerCommand(
        KEY_ENTER_COMMAND,
        (event) => {
          const e = event as KeyboardEvent | null;
          if (e && !e.shiftKey) {
            e.preventDefault();
            onSubmit?.();
            return true;
          }
          return false;
        },
        COMMAND_PRIORITY_HIGH,
      ),
    [editor, onSubmit],
  );
  return null;
}

/** Keep Lexical's editable state in sync with the `disabled` prop. */
function DisabledPlugin({ disabled }: { disabled?: boolean }) {
  const [editor] = useLexicalComposerContext();
  useEffect(() => {
    editor.setEditable(!disabled);
  }, [editor, disabled]);
  return null;
}

/**
 * A Lexical-backed text input — the structured-text foundation for the chat/query
 * composer (extensible to @gene mentions, tokens, etc.). Behaves like a multi-line
 * field: Enter submits, Shift+Enter newlines. Imperative `clear()`/`focus()` via ref.
 */
export const RichTextInput = forwardRef<RichTextInputHandle, RichTextInputProps>(
  function RichTextInput({ onChange, onSubmit, placeholder, disabled, autoFocus, className, ariaLabel }, ref) {
    const editorRef = useRef<LexicalEditor | null>(null);

    useImperativeHandle(
      ref,
      () => ({
        clear: () => editorRef.current?.dispatchCommand(CLEAR_EDITOR_COMMAND, undefined),
        focus: () => editorRef.current?.focus(),
      }),
      [],
    );

    const handleChange = (state: EditorState) => {
      state.read(() => onChange?.($getRoot().getTextContent()));
    };

    return (
      <LexicalComposer
        initialConfig={{
          namespace: "dogma-composer",
          editable: !disabled,
          onError: (e: Error) => console.error("Lexical:", e),
          theme: { paragraph: "m-0" },
        }}
      >
        <div className={cn("relative", className)}>
          <PlainTextPlugin
            contentEditable={
              <ContentEditable
                aria-label={ariaLabel}
                className="elev-sm max-h-40 min-h-[60px] w-full overflow-y-auto rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-signal focus:ring-1 focus:ring-signal"
              />
            }
            placeholder={
              <div className="pointer-events-none absolute left-3 top-2 select-none text-sm text-muted-foreground/70">
                {placeholder}
              </div>
            }
            ErrorBoundary={LexicalErrorBoundary}
          />
          <OnChangePlugin onChange={handleChange} ignoreSelectionChange />
          <HistoryPlugin />
          <ClearEditorPlugin />
          <DisabledPlugin disabled={disabled} />
          <EnterSubmitPlugin onSubmit={onSubmit} />
          <EditorRefPlugin editorRef={editorRef} />
          {autoFocus && <AutoFocusPlugin />}
        </div>
      </LexicalComposer>
    );
  },
);
