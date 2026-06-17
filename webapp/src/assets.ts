import logo from './app-assets/logo.jpeg';
import classicPreview from './app-assets/sound/Classic/Take_a_break.mp3';
import gentlePreview from './app-assets/sound/Gentle/Take_A_Moment.mp3';
import type { EndSound } from './types';

export const LOADING_IMAGE = logo;

export const SOUND_PREVIEWS: Record<EndSound, string> = {
  classic: classicPreview,
  gentle: gentlePreview,
};
