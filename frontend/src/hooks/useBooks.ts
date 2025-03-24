
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';

export interface Book {
  id: string;
  title: string;
  author: string;
  summary?: string;
  highlightCount: number;
  coverUrl?: string;
}

export interface Highlight {
  id: string;
  bookId: string;
  content: string;
  location?: string;
}

export const useBooks = () => {
  return useQuery({
    queryKey: ['books'],
    queryFn: async (): Promise<Book[]> => {
      const { data } = await apiClient.get('/api/v2/books');
      return data;
    }
  });
};

export const useBook = (title: string) => {
  return useQuery({
    queryKey: ['book', title],
    queryFn: async (): Promise<Book> => {
      const { data } = await apiClient.get(`/api/v2/books/${encodeURIComponent(title)}`);
      return data;
    },
    enabled: !!title
  });
};

export const useBookHighlights = (bookId: string) => {
  return useQuery({
    queryKey: ['bookHighlights', bookId],
    queryFn: async (): Promise<Highlight[]> => {
      const { data } = await apiClient.get(`/api/v2/books/${bookId}/highlights`);
      return data;
    },
    enabled: !!bookId
  });
};

export const useFetchCoverImage = (title: string, author: string) => {
  return useQuery({
    queryKey: ['bookCover', title, author],
    queryFn: async (): Promise<string> => {
      const { data } = await apiClient.get('/api/v2/books/cover', {
        params: { title, author }
      });
      return data.coverUrl;
    },
    enabled: !!title && !!author
  });
};
