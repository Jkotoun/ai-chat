import Typography from "@mui/material/Typography";
import ChatBubble from "./ChatBubble";
import type { Question } from "./messages";

type UserMessageProps = { question: Question };

export default function UserMessage({ question }: UserMessageProps) {
  return (
    <ChatBubble side="right" sx={{ bgcolor: "primary.main", color: "primary.contrastText" }}>
      <Typography sx={{ whiteSpace: "pre-wrap" }}>{question.text}</Typography>
    </ChatBubble>
  );
}
