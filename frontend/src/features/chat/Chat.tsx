"use client";

import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import MessageList from "./MessageList";
import QuestionForm from "./QuestionForm";
import { useChat } from "./useChat";

export default function Chat() {
  const { messages, isAnswering, ask } = useChat();

  return (
    <Container maxWidth="md">
      <Stack spacing={2} sx={{ minHeight: "100dvh", py: 2 }}>
        <Typography variant="h5" component="h1">
          AI support
        </Typography>
        <Stack sx={{ flex: 1 }}>
          <MessageList messages={messages} />
        </Stack>
        <QuestionForm disabled={isAnswering} onAsk={ask} />
      </Stack>
    </Container>
  );
}
