import { apiClient } from './api';
import { getCurrentTabUrl } from './current-tab';
import { initializePopup } from './popup';
import './styles.css';

void initializePopup({
  getCurrentTabUrl,
  getHealth: apiClient.getHealth,
});
