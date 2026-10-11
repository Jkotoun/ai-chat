import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import { useEffect, useRef } from "react";
import AssistantMessage from "./AssistantMessage";
import type { Message } from "./messages";
import UserMessage from "./UserMessage";

type MessageListProps = { messages: Message[] };

/** Keeps the newest message in view as messages arrive or grow. */
function useScrollToBottom(messages: Message[]) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Instant, since a smooth scroll would restart on every streamed token.
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);
  return bottomRef;
}

function MessageItem({ message }: { message: Message }) {
  if (message.role === "user") return <UserMessage question={message} />;
  return <AssistantMessage answer={message} />;
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useScrollToBottom(messages);
  return (
    <Stack spacing={2} aria-live="polite">
      {/* The list is append-only, so indexes are stable keys. */}
      {messages.map((message, index) => (
        <MessageItem key={index} message={message} />
      ))}
      <Box ref={bottomRef} />
    </Stack>
  );
}
