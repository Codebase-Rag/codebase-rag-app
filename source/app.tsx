import React, { useState, useEffect, useCallback } from 'react';

import { Box, Text, useApp, Static } from 'ink';
import Header from './components/Header.js';
import Message from './components/Message.js';
import Input from './components/Input.js';
import TreeAnimation from './components/TreeAnimation.js';
import { sendMessage, rejectChange } from './api/chat.js';
import { useSocket } from './contexts/SocketContext.js';
import { getWorkspaceInfo } from './utils/workspace.js';
import { useWorkspace } from './contexts/WorkspaceContext.js';
import SelectInput from 'ink-select-input';

type MessageItem = {
	role: 'user' | 'model';
	text: string;
	edit: boolean;
};

export default function App() {
	const {exit} = useApp();
	const { socket, isConnected, isConnecting, connectionError } = useSocket();
	const { workspace, setWorkspace } = useWorkspace();
	const [messages, setMessages] = useState<MessageItem[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [sessionId, setSessionId] = useState<string | null>(null);
	const [mode, setMode] = useState<string | null>(null);
	const [pendingReview, setPendingReview] = useState(false);
	const modes = [
		{
			label: 'Chat', 
			value: 'chat'
		}, 
		{
			label: 'Agent', 
			value: 'agent'
		}
	]

	const [showAnimation, setShowAnimation] = useState(true);

	const handleAnimationComplete = useCallback(() => {
		setShowAnimation(false);
	}, []);

	const reviewChoices = [
		{ label: '✅ Accept changes', value: 'accept' },
		{ label: '❌ Reject changes', value: 'reject' },
	];

	const handleReviewSelect = async (item: { value: string }) => {
		if (item.value === 'accept') {
			setMessages((prev) => [...prev, { role: 'model', text: 'Changes accepted.', edit: false }]);
			setPendingReview(false);
		} else if (item.value === 'reject') {
			if (!socket || !isConnected || !socket.id || !sessionId) {
				setMessages((prev) => [...prev, { role: 'model', text: 'Cannot reject: not connected or no active session.', edit: false }]);
				setPendingReview(false);
				return;
			}
			try {
				const res = await rejectChange(socket.id, sessionId);
				setMessages((prev) => [...prev, { role: 'model', text: res.response, edit: false }]);
			} catch (err: unknown) {
				const message = err instanceof Error ? err.message : 'Unknown error occurred';
				setMessages((prev) => [...prev, { role: 'model', text: `Error rejecting changes: ${message}`, edit: false }]);
			}
			setPendingReview(false);
		}
	};

	const welcomeMessage = 'Start you session by entering the path to your repository';

	useEffect(() => {
		setMessages([{role: 'model', text: welcomeMessage, edit: false}]);
	}, []); // Only run once on mount

	const handleSubmit = async (text: string) => {
		if (text === '/help') {
			const helpText = `Available commands:
• /help - Show this help message
• /clear - Clear conversation
• /quit - Leave current session and reset workspace
• /exit - Exit the application
• /agent - Switch to agent mode
• /chat - Switch to chat mode`;
			setMessages((prev) => [...prev, {role: 'model', text: helpText, edit: false}]);
		}

		if (text === '/exit') {
			exit();
			socket?.disconnect()
			return;
		}

		if (text === '/clear') {
			setMessages([]);
			return;
		}

		if (text === '/quit') {
			setSessionId(null);
			setWorkspace(process.cwd());
			setMessages([{role: 'model', text: welcomeMessage, edit: false}]);
			return;
		}

		// if (text === '/agent') {
		// 	setMode('agent');
		// 	setMessages((prev) => [...prev, {role: 'model', text: 'Switched to agent mode'}]);
		// 	return;
		// }

		// if (text === '/chat') {
		// 	setMode('chat');
		// 	setMessages((prev) => [...prev, {role: 'model', text: 'Switched to chat mode'}]);
		// 	return;
		// }

		setMessages((prev) => [...prev, {role: 'user', text, edit: false}]);

		if(workspace == process.cwd()) {
			try {
				const info = await getWorkspaceInfo(text);
				if(info.exists && info.isDirectory) {
					setWorkspace(info.absolutePath)
					setMessages((prev) => [...prev, {role: 'model', text: `Workspace is set to: ${info.absolutePath}`, edit: false}]);
				} else if (info.exists) {
					setMessages((prev) => [...prev, {role: 'model', text: 'Path exists but is not a directory. Please enter a valid directory path.', edit: false}]);
				} else {
					setMessages((prev) => [...prev, {role: 'model', text: 'Directory does not exist. Please enter a valid project directory path.', edit: false}]);
				}
			} catch (err: unknown) {
				const message = err instanceof Error ? err.message : 'Unknown error occurred';
				setMessages((prev) => [...prev, {role: 'model', text: `Error validating path: ${message}`, edit: false}]);
			}
			return;
		}

		setIsLoading(true);
		setError(null);

		if (!socket || !isConnected || !socket.id) {
			setMessages((prev) => [...prev, {role: 'model', text: 'Failed to connect to server', edit: false}]);
			return;
		}

		try {
			if (sessionId) {
				const res = await sendMessage(text, socket.id, mode!, sessionId);
				setMessages((prev) => [...prev, {role: 'model', text: res.response, edit: res.edit}]);
				if (res.edit) setPendingReview(true);
			} else {
				const res = await sendMessage(text, socket.id, mode!);
				setSessionId(res.session_id);
				setMessages((prev) => [...prev, {role: 'model', text: res.response, edit: res.edit}]);
				if (res.edit) setPendingReview(true);
			}
		} catch (err: unknown) {
			const message =
				err instanceof Error ? err.message : 'Unknown error occurred';
			setError(`Error: ${message}`);
		} finally {
			setIsLoading(false);
		}
	};
	if (showAnimation) {
		return <TreeAnimation onComplete={handleAnimationComplete} />;
	}
	return (
		<Box flexDirection="column" padding={1}>
			<Header />
			{(!mode) && (
				<SelectInput items={modes} onSelect={m => setMode(m.value)} />
			)}
			{(mode) && (
				<Static items={messages}>
					{(msg, i) => (
						<Message key={i} role={msg.role} text={msg.text} edit={msg.edit} />
					)}
				</Static>
			)}
			{(error || connectionError) && (
				<Box marginTop={1}>
					<Text color="red">{error || connectionError}</Text>
				</Box>
			)}
			{isConnecting && (
				<Box marginTop={1}>
					<Text color="yellow">Connecting to server...</Text>
				</Box>
			)}
			{!isConnected && !isConnecting && !connectionError && (
				<Box marginTop={1}>
					<Text color="gray">Disconnected from server</Text>
				</Box>
			)}
			{mode && pendingReview && (
				<Box flexDirection="column" marginTop={1}>
					<Text color="yellow" bold>Review changes — accept or reject?</Text>
					<SelectInput items={reviewChoices} onSelect={handleReviewSelect} />
				</Box>
			)}
			{mode && !pendingReview && (
				<Box marginTop={1}>
					<Input onSubmit={handleSubmit} isLoading={isLoading} mode={mode} />
				</Box>
			)}
		</Box>
	);
}
