import Box from "@mui/material/Box";
import Markdown from "react-markdown";

const markdownSx = {
  typography: "body1",
  lineHeight: 1.6,
  "& p": { m: 0 },
  "& p + p, & p + ul, & p + ol, & ul + p, & ol + p": { mt: 1 },
  "& ul, & ol": { my: 0, pl: 2.5 },
  "& strong": { fontWeight: 600 },
  "& code": { fontFamily: "monospace", fontSize: "0.9em" },
  "& a": { color: "primary.main" },
};

type MarkdownTextProps = { text: string };

/** Renders the model's Markdown (bold, lists, code) in the theme's typography. */
export default function MarkdownText({ text }: MarkdownTextProps) {
  return (
    <Box sx={markdownSx}>
      <Markdown>{text}</Markdown>
    </Box>
  );
}
