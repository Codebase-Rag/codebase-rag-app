#!/usr/bin/env node
import React from 'react';
import {render} from 'ink';
import App from './app.js';
import { SocketProvider } from './contexts/SocketContext.js';
import { WorkspaceProvider } from './contexts/WorkspaceContext.js';
import { config } from 'dotenv';

config()

render(
	<WorkspaceProvider >
		<SocketProvider>
			<App />
		</SocketProvider>
	</WorkspaceProvider >
);
