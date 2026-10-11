import Box from "@mui/material/Box";
import type { SxProps, Theme } from "@mui/material/styles";
import type { ReactNode } from "react";

type ChatBubbleProps = { side: "left" | "right"; sx?: SxProps<Theme>; children: ReactNode };

const SIDE_STYLES = {
  left: { alignSelf: "flex-start" },
  right: { alignSelf: "flex-end" },
} as const;

export default function ChatBubble({ side, sx, children }: ChatBubbleProps) {
  return (
    <Box
      sx={[
        { maxWidth: "85%", px: 1.5, py: 1, borderRadius: 2 },
        SIDE_STYLES[side],
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      {children}
    </Box>
  );
}
