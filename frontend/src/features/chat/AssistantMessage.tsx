import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ChatBubble from "./ChatBubble";
import MarkdownText from "./MarkdownText";
import type { Answer } from "./messages";
import SourceChips from "./SourceChips";
import TicketCard from "./TicketCard";
import TypingDots from "./TypingDots";

type AnswerProps = { answer: Answer };

function AnswerText({ answer }: AnswerProps) {
  if (answer.text) return <MarkdownText text={answer.text} />;
  if (answer.status === "streaming") return <TypingDots />;
  return null;
}

export default function AssistantMessage({ answer }: AnswerProps) {
  return (
    <Stack spacing={1} sx={{ alignSelf: "flex-start", maxWidth: "85%" }}>
      <ChatBubble side="left" sx={{ maxWidth: "none", bgcolor: "action.hover" }}>
        <AnswerText answer={answer} />
        {answer.error && (
          <Typography variant="body2" color="error">
            {answer.error}
          </Typography>
        )}
      </ChatBubble>
      {answer.ticketReference && <TicketCard reference={answer.ticketReference} />}
      <SourceChips sources={answer.sources} />
    </Stack>
  );
}
