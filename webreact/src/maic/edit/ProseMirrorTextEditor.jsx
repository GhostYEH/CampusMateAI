import React from "react";
import { baseKeymap, toggleMark } from "prosemirror-commands";
import { history, undo, redo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { DOMParser, DOMSerializer, Schema } from "prosemirror-model";
import { schema as basicSchema } from "prosemirror-schema-basic";
import { addListNodes } from "prosemirror-schema-list";
import { EditorState } from "prosemirror-state";
import { EditorView } from "prosemirror-view";

// Match the reference editor's document model closely enough for course slide
// text: paragraphs, headings, lists and inline emphasis are schema-checked on
// every parse.  The ProseMirror parser drops script/event attributes instead of
// reflecting arbitrary HTML back into the edit overlay.
const schema = new Schema({
  nodes: addListNodes(basicSchema.spec.nodes, "paragraph block*", "block"),
  marks: basicSchema.spec.marks,
});

function parseDocument(value) {
  const holder = document.createElement("div");
  holder.innerHTML = typeof value === "string" ? value : "";
  return DOMParser.fromSchema(schema).parse(holder);
}

function serializeDocument(documentNode) {
  const holder = document.createElement("div");
  const fragment = DOMSerializer.fromSchema(schema).serializeFragment(documentNode.content);
  holder.appendChild(fragment);
  return holder.innerHTML;
}

/**
 * Minimal React bridge around the same ProseMirror editing primitive used by
 * the reference project.  A single view owns the DOM; React only owns its
 * lifecycle and forwards the schema-normalized HTML after focus leaves it.
 */
export default function ProseMirrorTextEditor({ value, onCommit, className = "", style, ...rest }) {
  const hostRef = React.useRef(null);
  const viewRef = React.useRef(null);
  const valueRef = React.useRef(value || "");
  const commitRef = React.useRef(onCommit);
  const dirtyRef = React.useRef(false);
  const committedRef = React.useRef(false);

  valueRef.current = value || "";
  commitRef.current = onCommit;

  React.useEffect(() => {
    if (!hostRef.current) return undefined;
    dirtyRef.current = false;
    committedRef.current = false;
    const commitChanges = (editorView) => {
      if (!dirtyRef.current || committedRef.current) return;
      committedRef.current = true;
      commitRef.current?.(serializeDocument(editorView.state.doc));
    };
    const view = new EditorView(hostRef.current, {
      state: EditorState.create({
        doc: parseDocument(valueRef.current),
        plugins: [
          history(),
          keymap({
            "Mod-z": undo,
            "Mod-y": redo,
            "Mod-Shift-z": redo,
            "Mod-b": toggleMark(schema.marks.strong),
            "Mod-i": toggleMark(schema.marks.em),
          }),
          keymap(baseKeymap),
        ],
      }),
      dispatchTransaction(transaction) {
        if (transaction.docChanged) {
          dirtyRef.current = true;
          committedRef.current = false;
        }
        view.updateState(view.state.apply(transaction));
      },
      handleDOMEvents: {
        blur(editorView) {
          commitChanges(editorView);
          return false;
        },
      },
    });
    viewRef.current = view;
    view.focus();
    return () => {
      // React StrictMode runs one mount/cleanup probe in development.  A
      // schema-normalized document can serialize differently from the source
      // HTML even when the learner did nothing, so cleanup must only forward
      // an actual ProseMirror document transaction.
      commitChanges(view);
      view.destroy();
      viewRef.current = null;
    };
  }, []);

  return <div
    {...rest}
    ref={hostRef}
    className={`prosemirror-editor maic-edit-canvas__text-editor ${className}`.trim()}
    data-testid="openmaic-text-editor"
    role="textbox"
    aria-label="编辑文本元素"
    onPointerDown={(event) => event.stopPropagation()}
    style={style}
  />;
}
