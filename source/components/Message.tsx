import React from 'react';
import {Box, Text} from 'ink';
import Markdown from 'ink-markdown-es';

type Props = {
	role: 'user' | 'model';
	text: string;
	edit?: boolean;
};

export default function Message({role, text, edit}: Props) {
	if (role === 'user') {
		return (
			<Box>
				<Text color="green">{'> '}{text}</Text>
			</Box>
		);
	}

	return (
		<Box flexDirection="column">
			<Text color="blue" bold>Codebase Rag Agent:</Text>
			<Markdown>{text}</Markdown>
			{edit && (
				<Box marginLeft={2} marginTop={0}>
					<Text color="yellow">⚡ Code changes were applied</Text>
				</Box>
			)}
		</Box>
	);
}
