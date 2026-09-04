export type JobCapturePlatform = 'boss' | 'nowcoder';

export interface JobCaptureDraft {
  company: string;
  description: string;
  location: string;
  salaryText: string;
  source: JobCapturePlatform;
  sourceUrl: string;
  title: string;
}

export type JobCaptureResult =
  | {
      draft: JobCaptureDraft;
      warnings: string[];
    }
  | { status: 'unsupported'; platform?: JobCapturePlatform };
