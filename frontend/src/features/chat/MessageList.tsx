import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";
import type { Message } from "./messages";

type MessageListProps = { messages: Message[] };

function MessageItem({ message }: { message: Message }) {
  if (message.role === "user") return <UserMessage question={message} />;
  return <AssistantMessage answer={message} />;
}

export default function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Ask about plans, billing, sharing, or our terms.
      </Typography>
    );
  }
  return (
    <Stack spacing={1.5} aria-live="polite">
      {/* The list is append-only, so indexes are stable keys. */}
      {messages.map((message, index) => (
        <MessageItem key={index} message={message} />
      ))}
    </Stack>
  );
}
