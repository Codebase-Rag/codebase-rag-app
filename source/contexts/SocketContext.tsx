import React, { createContext, useContext, useEffect, useState, ReactNode, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { listDirectory, readFileBytes, readFileText, writeFile } from '../utils/file-operations.js';
import { useWorkspace } from './WorkspaceContext.js';
import { runCommand } from '../utils/shell-operations.js';

interface SocketContextType {
	socket: Socket | null;
	isConnected: boolean;
	isConnecting: boolean;
	connectionError: string | null;
	connect: () => void;
	disconnect: () => void;
}

const SocketContext = createContext<SocketContextType | undefined>(undefined);

interface SocketProviderProps {
	children: ReactNode;
	serverUrl?: string;
}

export const SocketProvider: React.FC<SocketProviderProps> = ({ 
	children, 
	serverUrl = process.env['BACKEND_URI'],
}) => {
	const [socket, setSocket] = useState<Socket | null>(null);
	const [isConnected, setIsConnected] = useState(false);
	const [isConnecting, setIsConnecting] = useState(false);
	const [connectionError, setConnectionError] = useState<string | null>(null);
	const { workspace } = useWorkspace();
    const workspaceRef = useRef<string>(workspace);
    useEffect(() => { workspaceRef.current = workspace; }, [workspace]);

	const connect = () => {
		if (socket && socket.connected) {
			return; // Already connected
		}

		setIsConnecting(true);
		setConnectionError(null);

		const newSocket = io(serverUrl, {
			autoConnect: true,
			reconnection: true,
			reconnectionAttempts: 5,
			reconnectionDelay: 1000,
		});

		newSocket.on('connect', () => {
			setIsConnected(true);
			setIsConnecting(false);
			setConnectionError(null);
		});

		newSocket.on('disconnect', (reason) => {
			setIsConnected(false);
			setIsConnecting(false);
			if (reason === 'io server disconnect') {
				// Server initiated disconnect, don't reconnect automatically
				setConnectionError('Server disconnected');
			}
		});

		newSocket.on('connect_error', (error) => {
			setIsConnecting(false);
			setConnectionError(`Failed to connect: ${error.message}`);
		});

		newSocket.on('reconnect', () => {
			setIsConnected(true);
			setIsConnecting(false);
			setConnectionError(null);
		});

		newSocket.on('reconnect_error', (error) => {
			setConnectionError(`Reconnection failed: ${error.message}`);
		});

		newSocket.on('reconnect_failed', () => {
			setIsConnecting(false);
			setConnectionError('Failed to reconnect to server');
		});

		// File system event handlers
		newSocket.on(
			'dir:list',
			async (
				payload: { dir_path: string },
				ack: (result: { ok: boolean; content?: string; error?: string }) => void
			) => {
				const result = await listDirectory(payload.dir_path, workspaceRef.current);
				ack(result as { ok: boolean; content?: string; error?: string });
			}
		);

		newSocket.on(
			'bytes:read',
			async (
				payload: { file_path: string },
				ack: (result: { ok: boolean; content?: Uint8Array; error?: string }) => void
			) => {
				const result = await readFileBytes(payload.file_path, workspaceRef.current);
				ack(result as { ok: boolean; content?: Uint8Array; error?: string });
			}
		);

		newSocket.on(
			'file:read',
			async (
				payload: { file_path: string },
				ack: (result: { ok: boolean; content?: string; error?: string }) => void
			) => {
				const result = await readFileText(payload.file_path, workspaceRef.current);
				ack(result as { ok: boolean; content?: string; error?: string });
			}
		);

		newSocket.on(
			'file:write',
			async (
				payload: { file_path: string; content: string },
				ack: (result: { ok: boolean; content?: string; error?: string }) => void
			) => {
				const result = await writeFile(payload.file_path, payload.content, workspaceRef.current);
				ack(result as { ok: boolean; content?: string; error?: string });
			}
		);

		newSocket.on(
			"command:run",
			async (
				payload: { cmd_parts: string[], timeout: number },
				ack: (result: { stdout?: string; stderr?: string; return_code?: number }) => void
			) => {
				const res = await runCommand(payload.cmd_parts, workspaceRef.current, payload.timeout);
				ack(res)
			}
		);

		setSocket(newSocket);
	};

	const disconnect = () => {
		if (socket) {
			socket.disconnect();
			setSocket(null);
			setIsConnected(false);
			setIsConnecting(false);
			setConnectionError(null);
		}
	};

	useEffect(() => {
		// Auto-connect on mount if serverUrl is available
		if (serverUrl) {
			connect();
		}

		return () => {
			if (socket) {
				socket.disconnect();
			}
		};
	}, [serverUrl]);

	const value: SocketContextType = {
		socket,
		isConnected,
		isConnecting,
		connectionError,
		connect,
		disconnect,
	};

	return (
		<SocketContext.Provider value={value}>
			{children}
		</SocketContext.Provider>
	);
};

export const useSocket = (): SocketContextType => {
	const context = useContext(SocketContext);
	if (context === undefined) {
		throw new Error('useSocket must be used within a SocketProvider');
	}
	return context;
};

export default SocketContext;