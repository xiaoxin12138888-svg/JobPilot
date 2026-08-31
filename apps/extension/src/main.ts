import { initializePopup } from './popup';
import './styles.css';

void initializePopup({
  sendMessage: (request) => chrome.runtime.sendMessage(request),
});
