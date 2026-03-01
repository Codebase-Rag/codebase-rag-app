import React, {useState} from 'react';
import {Box, Text} from 'ink';
import TextInput from 'ink-text-input';

type Props = {
	onSubmit: (value: string) => void;
	isLoading: boolean;
	mode: string;
};

export default function Input({onSubmit, isLoading, mode}: Props) {
	const [value, setValue] = useState('');

	const handleSubmit = (text: string) => {
		if (text.trim().length === 0) {
			return;
		}

		onSubmit(text.trim());
		setValue('');
	};

	if (isLoading) {
		return (
			<Box>
				<Text dimColor>Thinking...</Text>
			</Box>
		);
	}

	return (
		<Box>
			<Text color="cyan">[{mode}]</Text>
			<Text bold color="green">{' > '}</Text>
			<TextInput
				value={value}
				onChange={setValue}
				onSubmit={handleSubmit}
				placeholder="Type a message..."
				focus={!isLoading}
			/>
		</Box>
	);
}
