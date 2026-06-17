import { type ReactNode, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import {
  buildSubmission,
  type InputDestination,
  type InputReference,
  type InputSubmission,
  type SubmitMode,
} from "../../lib/ioContracts";
import { loadState, saveState } from "../../persist";
import type { ChatSendResult } from "../../types";
import Composer from "../Composer";

/* The one typed input surface (I/O rebuild). Every chat-like surface — controller
   dock, provider chats, task continuation — uses InputComposer. It wraps the shared
   Composer textarea and produces a typed InputSubmission whose destination + intent
   are explicit fields (never inferred from ambient UI state or prose). It owns the
   draft lifecycle: drafts persist per (workspace, destination) and survive reload,
   clear only on a confirmed submit, and are preserved on a failed submit. */

function destinationKey(d: InputDestination): string {
  if (d.kind === "controller") return "controller";
  if (d.kind === "provider") return `provider:${d.provider}`;
  return `task:${d.taskId}`;
}

function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `sub-${Date.now()}-${Math.floor(performance.now())}`;
  }
}

export default function InputComposer({
  workspaceId,
  destination,
  context,
  submitMode = "message",
  references = [],
  placeholder,
  contextChips,
  leading,
  busy = false,
  disabled = false,
  onStop,
  onResult,
  sendTitle = "Send",
}: {
  workspaceId: string;
  destination: InputDestination;
  /** Extra context carried in the submission (e.g. the controller's engine pick). */
  context?: InputSubmission["context"];
  submitMode?: SubmitMode;
  references?: InputReference[];
  placeholder?: string;
  contextChips?: ReactNode;
  leading?: ReactNode;
  busy?: boolean;
  disabled?: boolean;
  onStop?: () => void;
  onResult?: (result: ChatSendResult) => void;
  sendTitle?: string;
}) {
  const draftKey = `draft.${workspaceId}.${destinationKey(destination)}`;
  const [value, setValue] = useState<string>(() => loadState<string>(draftKey, ""));
  const [submitting, setSubmitting] = useState(false);

  // Restore the draft when the destination (and thus its key) changes.
  useEffect(() => {
    setValue(loadState<string>(draftKey, ""));
  }, [draftKey]);

  const onChange = useCallback(
    (v: string) => {
      setValue(v);
      saveState(draftKey, v); // persist every keystroke so a reload never loses it
    },
    [draftKey],
  );

  const onSend = useCallback(async () => {
    const text = value.trim();
    if (!text || submitting) return;
    setSubmitting(true);
    const submission = buildSubmission({
      id: newId(),
      workspaceId,
      destination,
      text,
      references,
      context,
      submitMode,
      createdAt: new Date().toISOString(),
    });
    try {
      const result = await api.chatSubmit(submission);
      // Clear the draft only on a confirmed, non-error result; otherwise keep it so
      // the user can retry without retyping.
      if (result.status !== "error") {
        setValue("");
        saveState(draftKey, "");
      }
      onResult?.(result);
    } catch (e) {
      onResult?.({
        status: "error",
        message: e instanceof Error ? e.message : String(e),
      } as ChatSendResult);
    } finally {
      setSubmitting(false);
    }
  }, [
    value,
    submitting,
    workspaceId,
    destination,
    context,
    references,
    submitMode,
    draftKey,
    onResult,
  ]);

  return (
    <Composer
      value={value}
      onChange={onChange}
      onSend={() => void onSend()}
      onStop={onStop}
      busy={busy || submitting}
      disabled={disabled}
      placeholder={placeholder}
      contextChips={contextChips}
      leading={leading}
      sendTitle={sendTitle}
    />
  );
}
