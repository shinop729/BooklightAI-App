
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { Book, Highlight, BookResponse, BooksResponse, BookHighlightsResponse, BookCoverResponse } from '../types';

export const useBooks = () => {
  return useQuery({
    queryKey: ['books'],
    queryFn: async (): Promise<Book[]> => {
      const { data } = await apiClient.get<BooksResponse>('/api/books');
      return data.data;
    }
  });
};

export const useBook = (id: string) => {
  return useQuery({
    queryKey: ['book', id],
    queryFn: async (): Promise<Book> => {
      const { data } = await apiClient.get<BookResponse>(`/api/books/${id}`);
      return data.data;
    },
    enabled: !!id
  });
};

export const useBookHighlights = (bookId: string) => {
  return useQuery({
    queryKey: ['bookHighlights', bookId],
    queryFn: async (): Promise<Highlight[]> => {
      const { data } = await apiClient.get<BookHighlightsResponse>(`/api/books/${bookId}/highlights`);
      return data.data.items;
    },
    enabled: !!bookId
  });
};

export const useFetchCoverImage = (title: string, author: string) => {
  return useQuery({
    queryKey: ['bookCover', title, author],
    queryFn: async (): Promise<string> => {
      const { data } = await apiClient.get<BookCoverResponse>('/api/books/cover', {
        params: { title, author }
      });
      return data.data.coverUrl;
    },
    enabled: !!title && !!author
  });
};
