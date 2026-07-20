import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { RequestComposer } from './RequestComposer';
import { MAX_REQUEST_TEXT_LENGTH } from '../types/api';

function Harness({
  onSubmit,
  isLoading = false,
}: {
  onSubmit: (text: string) => void;
  isLoading?: boolean;
}) {
  const [value, setValue] = useState('');
  return (
    <RequestComposer
      value={value}
      onChange={setValue}
      onSubmit={onSubmit}
      isLoading={isLoading}
    />
  );
}

describe('RequestComposer', () => {
  it('labels the input so it is reachable by name', () => {
    render(<Harness onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('Request')).toBeInTheDocument();
  });

  it('mirrors the API max_length=4000 bound', () => {
    render(<Harness onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('Request')).toHaveAttribute(
      'maxlength',
      String(MAX_REQUEST_TEXT_LENGTH),
    );
  });

  it('disables submit until there is non-whitespace input', async () => {
    const user = userEvent.setup();
    render(<Harness onSubmit={vi.fn()} />);

    const submit = screen.getByRole('button', { name: 'Run request' });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    expect(submit).toBeEnabled();
  });

  it('submits the trimmed text when the button is clicked', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText('Request'), '  Show my open tickets  ');
    await user.click(screen.getByRole('button', { name: 'Run request' }));

    expect(onSubmit).toHaveBeenCalledWith('Show my open tickets');
  });

  it('submits on Enter but not on Shift+Enter', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);

    const input = screen.getByLabelText('Request');
    await user.type(input, 'Brief me on my day');

    await user.type(input, '{Shift>}{Enter}{/Shift}');
    expect(onSubmit).not.toHaveBeenCalled();

    await user.type(input, '{Enter}');
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('shows a running label and blocks submit while loading', () => {
    render(<Harness onSubmit={vi.fn()} isLoading />);
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled();
  });
});
