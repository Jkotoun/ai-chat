import Box from "@mui/material/Box";
import type { SxProps, Theme } from "@mui/material/styles";
import type { ReactNode } from "react";

type ChatBubbleProps = { side: "left" | "right"; sx?: SxProps<Theme>; children: ReactNode };

// The corner nearest the sender is squared off.
const SIDE_STYLES = {
  left: { alignSelf: "flex-start", borderBottomLeftRadius: 4 },
  right: { alignSelf: "flex-end", borderBottomRightRadius: 4 },
} as const;

export default function ChatBubble({ side, sx, children }: ChatBubbleProps) {
  return (
    <Box
      sx={[
        { maxWidth: "85%", px: 2, py: 1.25, borderRadius: 4 },
        SIDE_STYLES[side],
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      {children}
    </Box>
  );
}
