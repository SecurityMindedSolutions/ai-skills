#!/usr/bin/perl
# Strip lines inside fenced code blocks from a markdown file.
# Handles both top-level and indented code fences.
# Uses 1-$x toggle instead of !$x to avoid Perl scalar reference bug.
my $inside = 0;
while (<>) {
    if (/^\s*`{3}/) {
        $inside = 1 - $inside;
        next;
    }
    print unless $inside;
}
