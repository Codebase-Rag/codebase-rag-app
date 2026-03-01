import React from 'react';
import {Box, Text} from 'ink';

export default function Header() {
	return (
		<Box borderStyle="round" borderColor="cyan" paddingX={1}>
			<Text bold color="cyan">
				Codebase RAG Agent
			</Text>
		</Box>
	);
}
