"use client";

import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import ChatHeader from "./ChatHeader";
import EmptyState from "./EmptyState";
import MessageList from "./MessageList";
import QuestionForm from "./QuestionForm";
import { useChat } from "./useChat";

export default function Chat() {
  const { messages, isAnswering, ask } = useChat();
  const hasMessages = messages.length > 0;

  return (
    <Container maxWidth="md" disableGutters sx={{ height: "100dvh" }}>
      <Stack sx={{ height: 1 }}>
        <ChatHeader />
        <Stack sx={{ flex: 1, overflowY: "auto", px: 2, py: 3 }}>
          {hasMessages ? <MessageList messages={messages} /> : <EmptyState onAsk={ask} />}
        </Stack>
        <QuestionForm disabled={isAnswering} onAsk={ask} />
      </Stack>
    </Container>
  );
}
