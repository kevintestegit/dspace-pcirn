/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.util;

import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * Reject a stream exceeding its byte budget instead of returning truncated data.
 */
public class LimitedInputStream extends FilterInputStream {
    private final long limit;
    private long count;

    /**
     * @param input stream to constrain
     * @param limit maximum number of bytes, including zero
     */
    public LimitedInputStream(InputStream input, long limit) {
        super(input);
        if (limit < 0) {
            throw new IllegalArgumentException("Negative stream limit");
        }
        this.limit = limit;
    }

    @Override
    public int read() throws IOException {
        int value = in.read();
        if (value != -1) {
            account(1);
        }
        return value;
    }

    @Override
    public int read(byte[] bytes, int offset, int length) throws IOException {
        java.util.Objects.checkFromIndexSize(offset, length, bytes.length);
        long remaining = limit - count;
        int requested = remaining >= length ? length : (int) remaining + 1;
        int read = in.read(bytes, offset, requested);
        if (read > 0) {
            account(read);
        }
        return read;
    }

    @Override
    public long skip(long amount) throws IOException {
        byte[] buffer = new byte[8192];
        long skipped = 0;
        while (skipped < amount) {
            int read = read(buffer, 0, (int) Math.min(buffer.length, amount - skipped));
            if (read == -1) {
                break;
            }
            skipped += read;
        }
        return skipped;
    }

    @Override
    public boolean markSupported() {
        return false;
    }

    @Override
    public synchronized void reset() throws IOException {
        throw new IOException("Reset is not supported for a bounded stream");
    }

    private void account(int read) throws IOException {
        if (read > limit - count) {
            throw new IOException("Stream exceeds its byte limit");
        }
        count += read;
    }
}
